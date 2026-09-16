from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import Promotion


def applicable_promotions(price_report, at=None):
    """Return active promotions that can apply to an existing PriceReport.

    Promotions never mutate the stored PriceReport. This function is the read
    layer that overlays temporary commercial activity on top of the last
    observed normal price.
    """
    at = at or timezone.now()
    if not price_report.business_id:
        return Promotion.objects.none()

    branch_filter = Q(business_branch__isnull=True)
    if price_report.business_branch_id:
        branch_filter |= Q(business_branch_id=price_report.business_branch_id)

    scope_filter = Q(scope=Promotion.Scope.STOREWIDE)
    scope_filter |= Q(
        scope=Promotion.Scope.PRODUCT,
        targets__product_id=price_report.product_id,
    )

    if price_report.subcategory_id:
        scope_filter |= Q(
            scope=Promotion.Scope.CATEGORY,
            targets__subcategory_id=price_report.subcategory_id,
        )
        scope_filter |= Q(
            scope=Promotion.Scope.CATEGORY,
            targets__category_id=price_report.subcategory.category_id,
        )

    return (
        Promotion.objects.active(at)
        .filter(business_id=price_report.business_id)
        .filter(branch_filter)
        .filter(scope_filter)
        .select_related('business', 'business_branch')
        .prefetch_related('targets__product', 'targets__category', 'targets__subcategory')
        .distinct()
    )


def _candidate_price(base_price, promotion):
    base_price = Decimal(base_price)

    if promotion.deal_type == Promotion.DealType.PERCENT and promotion.discount_value is not None:
        multiplier = (Decimal('100') - promotion.discount_value) / Decimal('100')
        return max(Decimal('0'), (base_price * multiplier).quantize(Decimal('0.01'))), True

    if promotion.deal_type == Promotion.DealType.AMOUNT_OFF and promotion.discount_value is not None:
        return max(Decimal('0'), (base_price - promotion.discount_value).quantize(Decimal('0.01'))), True

    if promotion.deal_type == Promotion.DealType.FIXED_PRICE and promotion.special_price is not None:
        return promotion.special_price.quantize(Decimal('0.01')), False

    return None, True


def effective_price(price_report, at=None):
    """Return the best non-stacking promotion overlay for a PriceReport.

    Multiple promotions are deliberately not stacked. When more than one
    promotion applies, Wikonomi shows the lowest individually-derived price.
    This avoids inventing combinations that a retailer may not allow.
    """
    best = None
    for promotion in applicable_promotions(price_report, at=at):
        candidate, is_estimate = _candidate_price(price_report.price, promotion)
        if candidate is None:
            continue
        if best is None or candidate < best['effective_price']:
            best = {
                'regular_price': price_report.price,
                'effective_price': candidate,
                'promotion': promotion,
                'is_estimate': is_estimate,
                'based_on_stale_price': price_report.is_stale,
            }

    return best
