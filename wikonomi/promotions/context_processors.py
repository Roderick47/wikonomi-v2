from django.conf import settings


def commerce_features(request):
    staff_preview = request.user.is_authenticated and request.user.is_staff
    return {
        'promotions_enabled': getattr(settings, 'PROMOTIONS_ENABLED', False) or staff_preview,
    }
