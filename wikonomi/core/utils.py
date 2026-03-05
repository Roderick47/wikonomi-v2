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

def annotate_with_distance(queryset, user_lat, user_lng, radius_hexes=3):
    """
    Annotate queryset with distance from user's location using DB-level Haversine formula.
    Uses H3 pre-filtering to avoid calculating distance for distant results.
    Returns a QuerySet annotated with 'distance_km', sorted by distance.
    This operates entirely at the database level for maximum CPU/Memory scalability.
    """
    from django.db.models import F, FloatField, ExpressionWrapper
    from django.db.models.functions import ASin, Cos, Radians, Sin, Sqrt

    # Step 1: Use H3 to pre-filter to nearby hexagons (fast index-level filter)
    # This avoids calculating distance for reports that are completely outside the user's city/radius
    center = h3.latlng_to_cell(user_lat, user_lng, 9)
    nearby_hexes = list(h3.grid_disk(center, radius_hexes))
    
    queryset = queryset.filter(
        latitude__isnull=False, 
        longitude__isnull=False,
        h3_res9__in=nearby_hexes
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
    return queryset.annotate(distance_km=distance_expr).order_by('distance_km')
