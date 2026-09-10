from django import template

from core.models import PriceReport
from core.share_services import build_price_share_context

register = template.Library()


def _cached_price_share(report, request=None):
    if request is not None:
        cache = getattr(request, '_wikonomi_price_share_context', None)
        if cache is None:
            cache = {}
            setattr(request, '_wikonomi_price_share_context', cache)
        if report.pk in cache:
            return cache[report.pk]
        base_url = request.build_absolute_uri('/').rstrip('/')
    else:
        cache = None
        base_url = ''

    result = build_price_share_context(report, base_url=base_url)
    if cache is not None:
        cache[report.pk] = result
    return result


@register.simple_tag
def price_share_context(report, request=None):
    return _cached_price_share(report, request)


@register.simple_tag
def price_share_context_by_id(price_id, request=None):
    try:
        price_id = int(price_id)
    except (TypeError, ValueError):
        return None

    report = PriceReport.objects.select_related(
        'product', 'business', 'business_branch'
    ).filter(pk=price_id).first()
    if not report:
        return None
    return _cached_price_share(report, request)
