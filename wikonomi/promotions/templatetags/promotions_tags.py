from django import template
from django.conf import settings

from promotions.models import Promotion
from promotions.services import effective_price


register = template.Library()


def _enabled():
    return getattr(settings, 'PROMOTIONS_ENABLED', False)


@register.simple_tag
def effective_promotion_price(price_report):
    if not _enabled():
        return None
    return effective_price(price_report)


@register.simple_tag
def active_promotions_for_business(business, limit=4):
    if not _enabled() or business is None:
        return Promotion.objects.none()
    return (
        Promotion.objects.active()
        .filter(business=business)
        .select_related('business', 'business_branch')
        .prefetch_related('targets__product', 'targets__category', 'targets__subcategory')[:limit]
    )
