import logging

from django.db import DatabaseError


logger = logging.getLogger(__name__)


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
