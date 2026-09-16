from collections import defaultdict

from django import template
from django.conf import settings

from categories.models import Subcategory
from promotions.models import Promotion
from promotions.services import effective_price


register = template.Library()
SNAPSHOT_KEY = 'wikonomi_active_promotions_snapshot'


def _enabled(context=None):
    if context is not None and 'promotions_enabled' in context:
        return bool(context['promotions_enabled'])
    return getattr(settings, 'PROMOTIONS_ENABLED', False)


def _active_snapshot(context):
    """Load active promotions once for a rendered page, not once per price card."""
    snapshot = context.render_context.get(SNAPSHOT_KEY)
    if snapshot is not None:
        return snapshot

    promotions = list(
        Promotion.objects.active()
        .select_related('business', 'business_branch')
        .prefetch_related('targets')
    )

    by_business = defaultdict(list)
    category_ids = set()
    for promotion in promotions:
        by_business[promotion.business_id].append(promotion)
        for target in promotion.targets.all():
            if target.category_id:
                category_ids.add(target.category_id)

    subcategory_category_map = {}
    if category_ids:
        subcategory_category_map = dict(
            Subcategory.objects.filter(category_id__in=category_ids).values_list(
                'id', 'category_id'
            )
        )

    snapshot = {
        'by_business': by_business,
        'subcategory_category_map': subcategory_category_map,
    }
    context.render_context[SNAPSHOT_KEY] = snapshot
    return snapshot


@register.simple_tag(takes_context=True)
def effective_promotion_price(context, price_report):
    if not _enabled(context) or not price_report.business_id:
        return None

    snapshot = _active_snapshot(context)
    promotions = snapshot['by_business'].get(price_report.business_id, [])
    if not promotions:
        return None

    return effective_price(
        price_report,
        promotions=promotions,
        subcategory_category_map=snapshot['subcategory_category_map'],
    )


@register.simple_tag(takes_context=True)
def active_promotions_for_business(context, business, limit=4):
    if not _enabled(context) or business is None:
        return []

    snapshot = _active_snapshot(context)
    return snapshot['by_business'].get(business.pk, [])[:limit]
