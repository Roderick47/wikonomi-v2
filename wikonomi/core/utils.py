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
    Annotate queryset with distance from user's location using Haversine formula.
    Uses H3 pre-filtering to avoid calculating distance for distant results.
    Returns a list of objects with distance_km attribute, sorted by distance.
    """
    R = 6371  # Earth's radius in kilometers
    
    def haversine_distance(lat1, lng1, lat2, lng2):
        """Calculate distance between two points in km using Haversine formula"""
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    
    # Step 1: Use H3 to pre-filter to nearby hexagons (fast database-level filter)
    # This avoids calculating distance for reports that are clearly too far away
    center = h3.latlng_to_cell(user_lat, user_lng, 9)
    nearby_hexes = list(h3.grid_disk(center, radius_hexes))
    
    # Filter to reports with location data that are in nearby hexagons
    queryset = queryset.filter(
        latitude__isnull=False, 
        longitude__isnull=False,
        h3_res9__in=nearby_hexes
    )
    
    # Step 2: Calculate exact distance only for the pre-filtered results
    results = []
    for obj in queryset:
        obj.distance_km = haversine_distance(user_lat, user_lng, obj.latitude, obj.longitude)
        results.append(obj)
    
    # Step 3: Sort by distance (since we can't use order_by on annotated Python attributes)
    results.sort(key=lambda x: x.distance_km)
    
    return results
