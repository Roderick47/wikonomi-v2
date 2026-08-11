import math

from django.utils import timezone

from .models import CabStatus

FRESHNESS_MINUTES = 20


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(float(lat1)))
        * math.cos(math.radians(float(lat2)))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_available_drivers(latitude, longitude, limit=10):
    cutoff = timezone.now() - timezone.timedelta(minutes=FRESHNESS_MINUTES)
    statuses = CabStatus.objects.select_related('driver').filter(
        availability=CabStatus.Availability.AVAILABLE,
        last_updated__gte=cutoff,
        latitude__isnull=False,
        longitude__isnull=False,
        driver__is_active_listing=True,
        driver__is_verified=True,
    )
    results = []
    for status in statuses:
        distance = haversine_km(latitude, longitude, status.latitude, status.longitude)
        results.append({'status': status, 'driver': status.driver, 'distance_km': distance})
    return sorted(results, key=lambda item: item['distance_km'])[:limit]


def set_stale_statuses_offline(minutes=FRESHNESS_MINUTES):
    cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
    return CabStatus.objects.filter(
        availability=CabStatus.Availability.AVAILABLE,
        last_updated__lt=cutoff,
    ).update(availability=CabStatus.Availability.OFFLINE)
