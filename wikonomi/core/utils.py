import h3
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
