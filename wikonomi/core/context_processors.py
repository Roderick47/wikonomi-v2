import logging

from django.conf import settings
from django.db import DatabaseError


logger = logging.getLogger(__name__)


def map_config(request):
    # Only public browser tokens may be serialized into HTML.
    token = getattr(settings, 'MAPBOX_PUBLIC_TOKEN', '').strip()
    if not token.startswith('pk.'):
        token = ''
    return {'wikonomi_map_config': {
        'accessToken': token,
        'style': getattr(settings, 'MAPBOX_STYLE_URL', 'mapbox://styles/mapbox/streets-v12'),
    }}


def notifications_count(request):
    if request.user.is_authenticated:
        from core.models import Notification

        try:
            count = Notification.objects.filter(
                user=request.user,
                is_read=False,
            ).count()
        except DatabaseError:
            # Notification badges are non-critical. A transient database issue or
            # a deployment whose migrations are still settling must not prevent
            # authenticated users from loading every template on the site.
            logger.exception('Unable to load the unread notification count')
            count = 0
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}
