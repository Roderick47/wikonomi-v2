from dataclasses import dataclass
from decimal import Decimal

from catalog.value import build_basket_comparison, build_product_value_comparison
from core.models import Product

from .current_price_services import _current_state


def _money(value):
    return str(value) if value is not None else None


def _serialize_value_row(row):
    if not row:
        return None
    report = row['report']
    product = row['product']
    return {
        'rank': row.get('rank'),
        'product_id': product.pk,
        'product_name': product.name,
        'relationship': row['relationship'],
        'relationship_key': row['relationship_key'],
        'package': row['package_label'],
        'unit_price': _money(row['unit_price']),
        'unit_price_label': row['unit_price_label'],
        'observed_price': _money(report.price),
        'currency': report.currency,
        'business': report.get_business_display(),
        'business_id': report.business_id,
        'business_branch_id': report.business_branch_id,
        'observed_at': report.observed_at,
        'price_report_id': report.pk,
    }


def compare_current_prices(product_id, currency='PGK'):
    product = Product.objects.filter(pk=product_id).first()
    if not product:
        raise ValueError(f'Product {product_id} was not found.')

    state = _current_state(product, preferred_currency=(currency or 'PGK').upper()[:3])
    comparable = state['comparable_prices']
    best = comparable[0] if comparable else None
    worst = comparable[-1] if comparable else None
    savings_amount = None
    savings_percent = None
    if best and worst and best['id'] != worst['id']:
        best_price = Decimal(best['price'])
        worst_price = Decimal(worst['price'])
        if worst_price > best_price:
            savings_amount = worst_price - best_price
            savings_percent = (savings_amount / worst_price) * Decimal('100')

    return {
        'product': {
            'id': product.pk,
            'name': product.name,
        },
        'currency': state['comparison_currency'],
        'stale_after_days': state['stale_after_days'],
        'latest_known_store_count': state['latest_known_store_count'],
        'comparable_store_count': state['comparable_store_count'],
        'stale_excluded_count': state['stale_excluded_count'],
        'best_price': best,
        'highest_comparable_price': worst if len(comparable) > 1 else None,
        'potential_savings': {
            'amount': _money(savings_amount),
            'percent': _money(savings_percent),
        },
        'prices': state['latest_known_prices'],
        'note': (
            'Each row is the latest-known valid observation for one store/branch. '
            'Rows older than the stale cutoff remain visible but cannot win the current comparison.'
        ),
    }


def compare_product_value(product_id, currency='PGK'):
    product = Product.objects.select_related('category', 'identity').filter(pk=product_id).first()
    if not product:
        raise ValueError(f'Product {product_id} was not found.')

    comparison = build_product_value_comparison(
        product,
        currency=(currency or 'PGK').upper()[:3],
    )
    return {
        'product': {'id': product.pk, 'name': product.name},
        'available': comparison['available'],
        'reason': comparison.get('reason'),
        'currency': comparison['currency'],
        'stale_after_days': comparison['stale_after_days'],
        'candidate_product_count': comparison.get('candidate_product_count', 0),
        'best_value': _serialize_value_row(comparison.get('best_value')),
        'best_exact_product': _serialize_value_row(comparison.get('best_exact_product')),
        'alternative_savings': {
            'amount_per_reference_unit': _money(comparison.get('alternative_savings_amount')),
            'percent': _money(comparison.get('alternative_savings_percent')),
        },
        'rows': [_serialize_value_row(row) for row in comparison.get('rows', [])],
        'note': (
            'Unit-value ranking compares compatible package measurements. A lower unit price does not imply equal '
            'quality, brand preference, availability, or suitability.'
        ),
    }


@dataclass
class BasketItem:
    product: object
    quantity: int
    is_checked: bool = False
    item_name: str = ''

    @property
    def product_id(self):
        return self.product.pk


def _serialize_basket_line(line):
    report = line['report']
    product = line['product']
    return {
        'product_id': product.pk,
        'product_name': product.name,
        'quantity': line['quantity'],
        'unit_price': _money(line['unit_price']),
        'line_total': _money(line['line_total']),
        'price_report_id': report.pk,
        'business': report.get_business_display(),
        'business_id': report.business_id,
        'business_branch_id': report.business_branch_id,
        'observed_at': report.observed_at,
    }


def _serialize_store(store):
    if not store:
        return None
    return {
        'store_name': store['store_name'],
        'business_id': store['business'].pk if store.get('business') else None,
        'business_branch_id': store['business_branch'].pk if store.get('business_branch') else None,
        'coverage_count': store['coverage_count'],
        'coverage_total': store['coverage_total'],
        'coverage_percent': _money(store['coverage_percent']),
        'is_full_basket': store['is_full_basket'],
        'total': _money(store['total']),
        'items': [_serialize_basket_line(line) for line in store['items']],
    }


def compare_basket(items, currency='PGK'):
    if not items:
        raise ValueError('At least one basket item is required.')

    normalized = []
    product_ids = []
    for item in items:
        product_id = int(item['product_id'])
        quantity = int(item.get('quantity', 1))
        if product_id <= 0:
            raise ValueError('product_id must be greater than zero.')
        if quantity <= 0:
            raise ValueError('quantity must be greater than zero.')
        product_ids.append(product_id)
        normalized.append((product_id, quantity))

    products = Product.objects.in_bulk(set(product_ids))
    missing_ids = sorted(set(product_ids) - set(products))
    if missing_ids:
        raise ValueError(f'Products were not found: {missing_ids}.')

    basket_items = [
        BasketItem(product=products[product_id], quantity=quantity)
        for product_id, quantity in normalized
    ]
    comparison = build_basket_comparison(
        basket_items,
        currency=(currency or 'PGK').upper()[:3],
    )

    return {
        'currency': comparison['currency'],
        'stale_after_days': comparison['stale_after_days'],
        'product_item_count': comparison['product_item_count'],
        'full_basket_store_count': comparison['full_basket_store_count'],
        'cheapest_full_store': _serialize_store(comparison['cheapest_full_store']),
        'best_coverage_store': _serialize_store(comparison['best_coverage_store']),
        'stores': [_serialize_store(store) for store in comparison['store_rows']],
        'split_store': {
            'complete': comparison['split_complete'],
            'total': _money(comparison['split_total']),
            'items': [_serialize_basket_line(line) for line in comparison['split_lines']],
            'saving_vs_cheapest_complete_store': {
                'amount': _money(comparison['full_store_savings_amount']),
                'percent': _money(comparison['full_store_savings_percent']),
            },
        },
        'missing_current_price_products': [
            {'id': product.pk, 'name': product.name}
            for product in comparison['missing_products']
        ],
        'note': (
            'This basket compares the exact product IDs supplied and never substitutes alternatives. Split-store '
            'totals do not include transport, time, or other shopping costs.'
        ),
    }
