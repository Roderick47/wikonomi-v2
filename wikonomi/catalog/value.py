from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import ProductIdentity
from .services import normalize_text, parse_product_identity


VALUE_STALE_AFTER_DAYS = 90

# Unit prices are normalized to shopper-friendly reference quantities.
# This keeps packages such as 500 g and 1 kg directly comparable without
# changing the underlying product identity or exact-price comparison.
MEASURE_SPECS = {
    'g': {'dimension': 'mass', 'base_unit': 'g', 'factor': Decimal('1'), 'reference': Decimal('1000'), 'label': 'kg'},
    'kg': {'dimension': 'mass', 'base_unit': 'g', 'factor': Decimal('1000'), 'reference': Decimal('1000'), 'label': 'kg'},
    'ml': {'dimension': 'volume', 'base_unit': 'ml', 'factor': Decimal('1'), 'reference': Decimal('1000'), 'label': 'L'},
    'l': {'dimension': 'volume', 'base_unit': 'ml', 'factor': Decimal('1000'), 'reference': Decimal('1000'), 'label': 'L'},
    'cm': {'dimension': 'length', 'base_unit': 'cm', 'factor': Decimal('1'), 'reference': Decimal('100'), 'label': 'm'},
    'm': {'dimension': 'length', 'base_unit': 'cm', 'factor': Decimal('100'), 'reference': Decimal('100'), 'label': 'm'},
    'each': {'dimension': 'count', 'base_unit': 'each', 'factor': Decimal('1'), 'reference': Decimal('1'), 'label': 'each'},
}


@dataclass(frozen=True)
class ResolvedMeasure:
    base_name: str
    brand: str
    package_quantity: Decimal | None
    package_unit: str
    pack_count: int
    dimension: str
    total_base_quantity: Decimal | None
    unit_price_reference: Decimal | None
    unit_price_label: str


@dataclass(frozen=True)
class UnitPrice:
    amount: Decimal
    label: str
    total_base_quantity: Decimal
    dimension: str


def _store_key(report):
    if report.business_branch_id:
        return ('branch', report.business_branch_id)
    if report.business_id:
        return ('business', report.business_id)
    return None


def resolve_product_measure(product):
    """Return the safest measurable package information available for a product."""
    try:
        identity = product.identity
    except ProductIdentity.DoesNotExist:
        identity = None

    parsed = parse_product_identity(
        product.name,
        brand=identity.brand if identity else '',
        variant=identity.variant if identity else '',
        barcode=identity.barcode if identity else '',
        unit=identity.package_unit if identity else '',
    )

    quantity = (
        identity.package_quantity
        if identity and identity.package_quantity is not None
        else parsed.package_quantity
    )
    unit = identity.package_unit if identity and identity.package_unit else parsed.package_unit
    pack_count = (
        identity.pack_count
        if identity and identity.pack_count is not None
        else parsed.pack_count
    ) or 1
    brand = identity.brand if identity and identity.brand else parsed.brand

    spec = MEASURE_SPECS.get(unit)
    total_base_quantity = None
    reference = None
    label = ''
    dimension = ''
    if spec and quantity is not None and quantity > 0 and pack_count > 0:
        total_base_quantity = quantity * spec['factor'] * Decimal(pack_count)
        reference = spec['reference']
        label = spec['label']
        dimension = spec['dimension']

    return ResolvedMeasure(
        base_name=parsed.base_name,
        brand=brand,
        package_quantity=quantity,
        package_unit=unit,
        pack_count=pack_count,
        dimension=dimension,
        total_base_quantity=total_base_quantity,
        unit_price_reference=reference,
        unit_price_label=label,
    )


def unit_price_for_report(report, measure=None):
    measure = measure or resolve_product_measure(report.product)
    if (
        not measure.total_base_quantity
        or not measure.unit_price_reference
        or report.price is None
        or report.price <= 0
    ):
        return None
    amount = (report.price * measure.unit_price_reference) / measure.total_base_quantity
    return UnitPrice(
        amount=amount,
        label=measure.unit_price_label,
        total_base_quantity=measure.total_base_quantity,
        dimension=measure.dimension,
    )


def package_label(measure):
    if measure.package_quantity is None or not measure.package_unit:
        return 'Package size unknown'
    quantity = format(measure.package_quantity.normalize(), 'f')
    if '.' in quantity:
        quantity = quantity.rstrip('0').rstrip('.')
    single = f'{quantity} {measure.package_unit}'
    if measure.pack_count > 1:
        return f'{measure.pack_count} × {single}'
    return single


def _latest_current_reports(product_ids, *, currency='PGK', stale_after_days=VALUE_STALE_AFTER_DAYS):
    """Return one fresh latest observation per product and store/branch."""
    from core.models import PriceReport

    cutoff = timezone.now() - timedelta(days=stale_after_days)
    candidates = PriceReport.objects.filter(
        product_id__in=product_ids,
        currency=currency,
        marked_for_deletion=False,
        price__gt=0,
        observed_at__gte=cutoff,
    ).filter(
        Q(business__isnull=False) | Q(business_branch__isnull=False)
    ).select_related(
        'product',
        'product__category',
        'product__identity',
        'business',
        'business_branch',
    ).order_by(
        'product_id',
        'business_branch_id',
        'business_id',
        '-observed_at',
        '-id',
    )

    seen = set()
    latest = []
    for report in candidates:
        store_key = _store_key(report)
        if store_key is None:
            continue
        key = (report.product_id, store_key)
        if key in seen:
            continue
        seen.add(key)
        latest.append(report)
    return latest


def _candidate_products_for_value(product, measure):
    """
    Return a conservative product family for unit-value comparison.

    Candidates must share the same normalized base product name, measurement
    dimension, and (when known) category. Brand differences are allowed but are
    labelled as alternatives instead of being treated as exact substitutes.
    """
    from core.models import Product

    if not measure.base_name or not measure.dimension:
        return [product]

    qs = Product.objects.select_related('identity', 'category').all()
    if product.category_id:
        qs = qs.filter(category_id=product.category_id)

    candidates = []
    for candidate in qs:
        candidate_measure = resolve_product_measure(candidate)
        if not candidate_measure.dimension:
            continue
        if candidate_measure.dimension != measure.dimension:
            continue
        if normalize_text(candidate_measure.base_name) != normalize_text(measure.base_name):
            continue
        candidates.append(candidate)

    if product.pk not in {candidate.pk for candidate in candidates}:
        candidates.append(product)
    return candidates


def build_product_value_comparison(product, *, currency='PGK', stale_after_days=VALUE_STALE_AFTER_DAYS, limit=30):
    """Build unit-price rankings without altering exact-product price semantics."""
    currency = (currency or 'PGK').upper()[:3]
    product_measure = resolve_product_measure(product)
    if not product_measure.dimension:
        return {
            'available': False,
            'reason': 'package_size_unknown',
            'currency': currency,
            'product_measure': product_measure,
            'rows': [],
            'best_value': None,
            'best_exact_product': None,
            'alternative_savings_amount': None,
            'alternative_savings_percent': None,
            'stale_after_days': stale_after_days,
        }

    candidates = _candidate_products_for_value(product, product_measure)
    measures = {candidate.pk: resolve_product_measure(candidate) for candidate in candidates}
    reports = _latest_current_reports(
        [candidate.pk for candidate in candidates],
        currency=currency,
        stale_after_days=stale_after_days,
    )

    rows = []
    current_brand = normalize_text(product_measure.brand)
    for report in reports:
        measure = measures.get(report.product_id) or resolve_product_measure(report.product)
        unit_price = unit_price_for_report(report, measure)
        if unit_price is None or unit_price.dimension != product_measure.dimension:
            continue

        candidate_brand = normalize_text(measure.brand)
        if report.product_id == product.pk:
            relationship = 'Exact product'
            relationship_key = 'exact'
        elif current_brand and candidate_brand and current_brand == candidate_brand:
            relationship = 'Same brand, different pack size'
            relationship_key = 'same_brand'
        else:
            relationship = 'Comparable alternative'
            relationship_key = 'alternative'

        rows.append({
            'product': report.product,
            'report': report,
            'measure': measure,
            'package_label': package_label(measure),
            'unit_price': unit_price.amount,
            'unit_price_label': unit_price.label,
            'relationship': relationship,
            'relationship_key': relationship_key,
        })

    rows.sort(key=lambda row: (row['unit_price'], row['report'].price, -row['report'].observed_at.timestamp()))
    rows = rows[:limit]
    for index, row in enumerate(rows, start=1):
        row['rank'] = index

    best_value = rows[0] if rows else None
    exact_rows = [row for row in rows if row['relationship_key'] == 'exact']
    best_exact_product = min(exact_rows, key=lambda row: row['unit_price']) if exact_rows else None

    savings_amount = None
    savings_percent = None
    if (
        best_value
        and best_exact_product
        and best_value['product'].pk != product.pk
        and best_exact_product['unit_price'] > best_value['unit_price']
    ):
        savings_amount = best_exact_product['unit_price'] - best_value['unit_price']
        savings_percent = (savings_amount / best_exact_product['unit_price']) * Decimal('100')

    return {
        'available': bool(rows),
        'reason': None if rows else 'no_fresh_measurable_prices',
        'currency': currency,
        'product_measure': product_measure,
        'rows': rows,
        'best_value': best_value,
        'best_exact_product': best_exact_product,
        'alternative_savings_amount': savings_amount,
        'alternative_savings_percent': savings_percent,
        'candidate_product_count': len(candidates),
        'stale_after_days': stale_after_days,
    }


def build_basket_comparison(items, *, currency='PGK', stale_after_days=VALUE_STALE_AFTER_DAYS):
    """
    Compare an exact shopping basket across stores using fresh latest prices.

    The basket never substitutes another product automatically. Custom items and
    products without a fresh current price are surfaced as uncovered instead.
    """
    currency = (currency or 'PGK').upper()[:3]
    active_items = [item for item in items if not item.is_checked]
    product_items = [item for item in active_items if item.product_id]
    custom_items = [item for item in active_items if not item.product_id]

    quantity_by_product = {}
    item_by_product = {}
    for item in product_items:
        quantity_by_product[item.product_id] = quantity_by_product.get(item.product_id, 0) + item.quantity
        item_by_product.setdefault(item.product_id, item)

    product_ids = list(quantity_by_product)
    reports = _latest_current_reports(
        product_ids,
        currency=currency,
        stale_after_days=stale_after_days,
    ) if product_ids else []

    reports_by_product = {product_id: [] for product_id in product_ids}
    stores = {}
    for report in reports:
        reports_by_product.setdefault(report.product_id, []).append(report)
        store_key = _store_key(report)
        if store_key is None:
            continue
        store = stores.setdefault(store_key, {
            'store_key': store_key,
            'store_name': report.get_business_display(),
            'business': report.business,
            'business_branch': report.business_branch,
            'items': [],
            'covered_product_ids': set(),
            'total': Decimal('0'),
        })
        quantity = quantity_by_product.get(report.product_id, 0)
        if not quantity:
            continue
        line_total = report.price * quantity
        store['items'].append({
            'item': item_by_product[report.product_id],
            'product': report.product,
            'report': report,
            'quantity': quantity,
            'unit_price': report.price,
            'line_total': line_total,
        })
        store['covered_product_ids'].add(report.product_id)
        store['total'] += line_total

    total_product_items = len(product_ids)
    store_rows = []
    for store in stores.values():
        covered = len(store['covered_product_ids'])
        store['coverage_count'] = covered
        store['coverage_total'] = total_product_items
        store['coverage_percent'] = (
            (Decimal(covered) / Decimal(total_product_items)) * Decimal('100')
            if total_product_items else Decimal('0')
        )
        store['is_full_basket'] = bool(total_product_items and covered == total_product_items)
        store['items'].sort(key=lambda row: row['product'].name.casefold())
        store_rows.append(store)

    store_rows.sort(key=lambda row: (-row['coverage_count'], row['total'], row['store_name'].casefold()))
    full_basket_stores = sorted(
        [row for row in store_rows if row['is_full_basket']],
        key=lambda row: (row['total'], row['store_name'].casefold()),
    )
    cheapest_full_store = full_basket_stores[0] if full_basket_stores else None
    best_coverage_store = store_rows[0] if store_rows else None

    split_lines = []
    split_total = Decimal('0')
    missing_products = []
    for product_id in product_ids:
        product_reports = reports_by_product.get(product_id, [])
        if not product_reports:
            missing_products.append(item_by_product[product_id].product)
            continue
        best_report = min(product_reports, key=lambda report: (report.price, -report.observed_at.timestamp()))
        quantity = quantity_by_product[product_id]
        line_total = best_report.price * quantity
        split_total += line_total
        split_lines.append({
            'item': item_by_product[product_id],
            'product': best_report.product,
            'report': best_report,
            'quantity': quantity,
            'unit_price': best_report.price,
            'line_total': line_total,
        })

    split_complete = bool(product_ids) and not missing_products
    full_store_savings_amount = None
    full_store_savings_percent = None
    if cheapest_full_store and split_complete and cheapest_full_store['total'] > split_total:
        full_store_savings_amount = cheapest_full_store['total'] - split_total
        full_store_savings_percent = (
            full_store_savings_amount / cheapest_full_store['total']
        ) * Decimal('100')

    return {
        'currency': currency,
        'stale_after_days': stale_after_days,
        'product_item_count': total_product_items,
        'custom_item_count': len(custom_items),
        'custom_items': custom_items,
        'missing_products': missing_products,
        'store_rows': store_rows,
        'full_basket_stores': full_basket_stores,
        'full_basket_store_count': len(full_basket_stores),
        'cheapest_full_store': cheapest_full_store,
        'best_coverage_store': best_coverage_store,
        'split_lines': split_lines,
        'split_total': split_total if split_complete else None,
        'split_complete': split_complete,
        'full_store_savings_amount': full_store_savings_amount,
        'full_store_savings_percent': full_store_savings_percent,
    }
