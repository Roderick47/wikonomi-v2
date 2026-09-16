from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from categories.models import Subcategory

from .models import Promotion


def _subcategory_category_id(price_report, subcategory_category_map=None):
    """Return the parent category for a report without forcing an N+1 query."""
    if not price_report.subcategory_id:
        return None

    if subcategory_category_map is not None:
        return subcategory_category_map.get(price_report.subcategory_id)

    # Non-template callers normally use the SQL path in applicable_promotions,
    # but keep this fallback correct for callers that supply a promotion list.
    return Subcategory.objects.filter(pk=price_report.subcategory_id).values_list(
        'category_id', flat=True
    ).first()


def promotion_applies(promotion, price_report, subcategory_category_map=None):
    """Return whether one active promotion applies to one observed price.

    This matcher is intentionally conservative. A category promotion is only
    applied when Wikonomi already knows the report's subcategory/category; it
    never guesses a taxonomy match from product text.
    """
    if not price_report.business_id or promotion.business_id != price_report.business_id:
        return False

    if (
        promotion.business_branch_id
        and promotion.business_branch_id != price_report.business_branch_id
    ):
        return False

    if promotion.scope == Promotion.Scope.STOREWIDE:
        return True

    targets = list(promotion.targets.all())

    if promotion.scope == Promotion.Scope.PRODUCT:
        return any(target.product_id == price_report.product_id for target in targets)

    if promotion.scope == Promotion.Scope.CATEGORY:
        if not price_report.subcategory_id:
            return False

        if any(
            target.subcategory_id == price_report.subcategory_id
            for target in targets
            if target.subcategory_id
        ):
            return True

        category_id = _subcategory_category_id(
            price_report,
            subcategory_category_map=subcategory_category_map,
        )
        return bool(category_id) and any(
            target.category_id == category_id
            for target in targets
            if target.category_id
        )

    return False


def applicable_promotions(
    price_report,
    at=None,
    promotions=None,
    subcategory_category_map=None,
):
    """Return active promotions that can apply to an existing PriceReport.

    Promotions never mutate the stored PriceReport. When ``promotions`` is
    supplied (for example by the template snapshot), matching happens in
    Python so a page containing many price cards does not issue a promotion
    query for every card. Without a supplied list, callers retain the compact
    database-query path.
    """
    at = at or timezone.now()
    if not price_report.business_id:
        return [] if promotions is not None else Promotion.objects.none()

    if promotions is not None:
        return [
            promotion
            for promotion in promotions
            if promotion_applies(
                promotion,
                price_report,
                subcategory_category_map=subcategory_category_map,
            )
        ]

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
        .prefetch_related('targets')
        .distinct()
    )


def _candidate_price(base_price, promotion):
    base_price = Decimal(base_price)

    if promotion.deal_type == Promotion.DealType.PERCENT and promotion.discount_value is not None:
        multiplier = (Decimal('100') - promotion.discount_value) / Decimal('100')
        return max(
            Decimal('0'),
            (base_price * multiplier).quantize(Decimal('0.01')),
        ), True

    if promotion.deal_type == Promotion.DealType.AMOUNT_OFF and promotion.discount_value is not None:
        return max(
            Decimal('0'),
            (base_price - promotion.discount_value).quantize(Decimal('0.01')),
        ), True

    if promotion.deal_type == Promotion.DealType.FIXED_PRICE and promotion.special_price is not None:
        return promotion.special_price.quantize(Decimal('0.01')), False

    return None, True


def effective_price(
    price_report,
    at=None,
    promotions=None,
    subcategory_category_map=None,
):
    """Return the best non-stacking promotion overlay for a PriceReport.

    Multiple promotions are deliberately not stacked. When more than one
    promotion applies, Wikonomi shows the lowest individually-derived price.
    This avoids inventing combinations that a retailer may not allow.
    """
    best = None
    for promotion in applicable_promotions(
        price_report,
        at=at,
        promotions=promotions,
        subcategory_category_map=subcategory_category_map,
    ):
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
