def notifications_count(request):
    if request.user.is_authenticated:
        from core.models import Notification
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}
