import h3
import math
from .models import PriceReport

def get_nearby_prices(product, lat, lng, radius_hexes=2):
    """Return PriceReports of the same product in the same vicinity using H3"""
    if not lat or not lng:
        return PriceReport.objects.none()
    center = h3.latlng_to_cell(lat, lng, 9)
    neighbors = list(h3.grid_disk(center, radius_hexes))
    return PriceReport.objects.filter(
        product=product,
        h3_res9__in=neighbors
    ).select_related('user').order_by('-observed_at')

def annotate_with_distance(queryset, user_lat, user_lng, radius_hexes=3, radius_km=None):
    """
    Annotate queryset with distance from user's location using DB-level Haversine formula.
    Uses H3 pre-filtering to avoid calculating distance for distant results.
    Returns a QuerySet annotated with 'distance_km', sorted by distance.
    This operates entirely at the database level for maximum CPU/Memory scalability.
    """
    from django.db.models import F, FloatField, ExpressionWrapper
    from django.db.models.functions import ASin, Cos, Radians, Sin, Sqrt

    # Step 1: Bound candidates before the expensive distance expression.
    # Existing H3 callers keep their narrow hex filter. Discovery can opt into
    # a city-scale radius without enumerating thousands of H3 cells.
    if radius_km is None:
        center = h3.latlng_to_cell(user_lat, user_lng, 9)
        nearby_hexes = list(h3.grid_disk(center, radius_hexes))
        queryset = queryset.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            h3_res9__in=nearby_hexes,
        )
    else:
        latitude_delta = radius_km / 111.32
        longitude_delta = radius_km / (111.32 * max(abs(math.cos(math.radians(user_lat))), 0.01))
        queryset = queryset.filter(
            latitude__range=(max(-90, user_lat - latitude_delta), min(90, user_lat + latitude_delta)),
            longitude__range=(max(-180, user_lng - longitude_delta), min(180, user_lng + longitude_delta)),
        )
    
    # Step 2: Database-level exact distance calculation (Haversine)
    # Allows pagination (OFFSET/LIMIT) to happen in Postgres, preventing memory exhaustion
    R = 6371.0  # Earth's radius in kilometers
    
    lat1_rad = Radians(float(user_lat))
    lon1_rad = Radians(float(user_lng))
    lat2_rad = Radians(F('latitude'))
    lon2_rad = Radians(F('longitude'))
    
    dlat_2 = (lat2_rad - lat1_rad) / 2.0
    dlon_2 = (lon2_rad - lon1_rad) / 2.0
    
    # a = sin²(dLat/2) + cos(lat1)*cos(lat2)*sin²(dLon/2)
    # Note: For SQLite fallback if any, we use 'Power' carefully, but Postgres handles basic arithmetic cleanly.
    # To ensure cross-compatibility, we use django Power manually if needed, but math Operators '*' work fine.
    a = (Sin(dlat_2) * Sin(dlat_2)) + Cos(lat1_rad) * Cos(lat2_rad) * (Sin(dlon_2) * Sin(dlon_2))
    
    # c = 2 * arcsin(sqrt(a))
    c = 2.0 * ASin(Sqrt(a))
    
    distance_expr = ExpressionWrapper(R * c, output_field=FloatField())
    
    # Annotate and sort via database engine
    nearby = queryset.annotate(distance_km=distance_expr)
    if radius_km is not None:
        nearby = nearby.filter(distance_km__lte=radius_km)
    return nearby.order_by('distance_km', '-observed_at', '-pk')
