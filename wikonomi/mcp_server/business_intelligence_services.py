from collections import Counter
from decimal import Decimal

from django.db.models import Q

from core.models import Business, BusinessBranch, BusinessInventoryItem, PriceReport
from core.product_views import COMPARISON_STALE_AFTER_DAYS, _freshness_metadata, _store_key

from .current_price_services import _absolute_url


def _business_reports(business):
    return PriceReport.objects.filter(
        Q(business=business) | Q(business_branch__canonical_business=business),
        marked_for_deletion=False,
        price__gt=0,
    ).select_related('product', 'business', 'business_branch')


def _branch_reports(branch):
    return PriceReport.objects.filter(
        business_branch=branch,
        marked_for_deletion=False,
        price__gt=0,
    ).select_related('product', 'business', 'business_branch')


def _latest_per_product_store(reports):
    """Return one latest report per product, store/location, and currency."""
    seen = set()
    latest = []
    for report in reports.order_by('-observed_at', '-id'):
        store_key = _store_key(report)
        if store_key is None:
            continue
        key = (report.product_id, store_key, (report.currency or '').upper())
        if key in seen:
            continue
        seen.add(key)
        latest.append(report)
    return latest


def _current_rows(reports, currency='PGK', include_stale=False):
    currency = (currency or 'PGK').upper()
    rows = []
    for report in _latest_per_product_store(reports):
        if (report.currency or '').upper() != currency:
            continue
        freshness = _freshness_metadata(report.observed_at)
        if freshness['key'] == 'stale' and not include_stale:
            continue
        branch = report.business_branch
        rows.append({
            'price_report_id': report.pk,
            'product_id': report.product_id,
            'product_name': report.product.name,
            'price': str(report.price),
            'currency': report.currency,
            'business_id': report.business_id or (branch.canonical_business_id if branch else None),
            'business_name': report.get_business_display(),
            'branch_id': report.business_branch_id,
            'branch_name': branch.name if branch else None,
            'observed_at': report.observed_at,
            'freshness': freshness['key'],
            'freshness_label': freshness['label'],
            'age_days': freshness['age_days'],
            'evidence_count': report.get_photo_count(),
            'product_url': _absolute_url(f'/product/{report.product_id}/'),
            'price_url': _absolute_url(f'/price/{report.pk}/'),
        })
    rows.sort(key=lambda row: (row['product_name'].casefold(), Decimal(row['price']), row['branch_name'] or ''))
    return rows


def _coverage(reports):
    latest = _latest_per_product_store(reports)
    latest_products = {report.product_id for report in latest}
    current = []
    currencies = Counter()
    for report in latest:
        freshness = _freshness_metadata(report.observed_at)
        if freshness['key'] != 'stale':
            current.append(report)
            currencies[(report.currency or '').upper()] += 1
    current_products = {report.product_id for report in current}
    latest_observed = max((report.observed_at for report in latest), default=None)
    latest_current_observed = max((report.observed_at for report in current), default=None)
    return {
        'stale_after_days': COMPARISON_STALE_AFTER_DAYS,
        'latest_known_report_count': len(latest),
        'current_report_count': len(current),
        'latest_known_product_count': len(latest_products),
        'current_product_count': len(current_products),
        'stale_only_product_count': len(latest_products - current_products),
        'current_currency_report_counts': dict(sorted(currencies.items())),
        'latest_observed': latest_observed,
        'latest_current_observed': latest_current_observed,
    }


def _branch_profile(branch, include_coverage=True):
    payload = {
        'id': branch.pk,
        'business_id': branch.canonical_business_id,
        'business_name': branch.canonical_business.name,
        'name': branch.name,
        'slug': branch.slug,
        'address': branch.address or None,
        'latitude': branch.latitude,
        'longitude': branch.longitude,
        'phone': branch.phone or None,
        'email': branch.email or None,
        'is_main_branch': branch.is_main_branch,
        'is_active': branch.is_active,
    }
    if include_coverage:
        payload['price_coverage'] = _coverage(_branch_reports(branch))
    return payload


def _inventory_summary(business, limit=25):
    items = BusinessInventoryItem.objects.filter(business=business).select_related('product').order_by('-updated_at', '-id')
    count = items.count()
    recent = []
    for item in items[:limit]:
        recent.append({
            'product_id': item.product_id,
            'product_name': item.product.name,
            'sku': item.sku or None,
            'barcode': item.barcode or None,
            'brand': item.brand or None,
            'unit': item.unit or None,
            'stock_quantity': str(item.stock_quantity) if item.stock_quantity is not None else None,
            'updated_at': item.updated_at,
            'product_url': _absolute_url(f'/product/{item.product_id}/'),
        })
    return {
        'scope': 'business_wide',
        'branch_specific': False,
        'item_count': count,
        'recent_items': recent,
        'note': 'Inventory imports are currently business-wide. Do not infer that an item is stocked at a specific branch unless branch-specific price or inventory evidence exists.',
    }


def _group_business_products(rows, limit=50):
    grouped = {}
    for row in rows:
        group = grouped.setdefault(row['product_id'], {
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'currency': row['currency'],
            'location_count': 0,
            'min_price': None,
            'max_price': None,
            'latest_observed': None,
            'best_price': None,
            'locations': [],
            'product_url': row['product_url'],
        })
        price = Decimal(row['price'])
        group['location_count'] += 1
        group['min_price'] = price if group['min_price'] is None else min(group['min_price'], price)
        group['max_price'] = price if group['max_price'] is None else max(group['max_price'], price)
        if group['latest_observed'] is None or row['observed_at'] > group['latest_observed']:
            group['latest_observed'] = row['observed_at']
        if group['best_price'] is None or price < Decimal(group['best_price']['price']):
            group['best_price'] = row
        group['locations'].append({
            'branch_id': row['branch_id'],
            'branch_name': row['branch_name'],
            'price': row['price'],
            'observed_at': row['observed_at'],
            'freshness': row['freshness'],
        })

    products = []
    for group in grouped.values():
        group['min_price'] = str(group['min_price']) if group['min_price'] is not None else None
        group['max_price'] = str(group['max_price']) if group['max_price'] is not None else None
        group['locations'].sort(key=lambda location: (Decimal(location['price']), location['branch_name'] or ''))
        products.append(group)
    products.sort(key=lambda item: item['product_name'].casefold())
    return products[:limit]


def get_business(business_id, *, product_query='', currency='PGK', limit=50, include_inventory=True):
    business = Business.objects.select_related('business_subcategory').filter(pk=business_id).first()
    if not business:
        raise ValueError(f'Business {business_id} was not found.')

    reports = _business_reports(business)
    if product_query:
        reports = reports.filter(
            Q(product__name__icontains=product_query)
            | Q(product__aliases__alias_name__icontains=product_query)
            | Q(product__tags__name__icontains=product_query)
        ).distinct()

    current_rows = _current_rows(reports, currency=currency, include_stale=False)
    branches = [
        _branch_profile(branch)
        for branch in business.branches.select_related('canonical_business').order_by('-is_main_branch', 'name')
    ]
    direct_reports = PriceReport.objects.filter(
        business=business,
        business_branch__isnull=True,
        marked_for_deletion=False,
        price__gt=0,
    ).select_related('product', 'business', 'business_branch')

    subcategory = business.business_subcategory
    payload = {
        'id': business.pk,
        'name': business.name,
        'details': business.details or '',
        'subcategory': getattr(subcategory, 'name', None) if subcategory else None,
        'url': _absolute_url(f'/business/{business.pk}/'),
        'price_coverage': _coverage(_business_reports(business)),
        'unassigned_business_level_price_coverage': _coverage(direct_reports),
        'branch_count': len(branches),
        'active_branch_count': sum(1 for branch in branches if branch['is_active']),
        'branches': branches,
        'currency': (currency or 'PGK').upper(),
        'product_query': product_query or None,
        'current_products': _group_business_products(current_rows, limit=limit),
        'current_product_count_returned': min(len({row['product_id'] for row in current_rows}), limit),
    }
    if include_inventory:
        payload['business_inventory'] = _inventory_summary(business, limit=min(limit, 25))
    return payload


def get_branch(branch_id, *, product_query='', currency='PGK', limit=50, include_stale=False):
    branch = BusinessBranch.objects.select_related('canonical_business').filter(pk=branch_id).first()
    if not branch:
        raise ValueError(f'Business branch {branch_id} was not found.')

    reports = _branch_reports(branch)
    if product_query:
        reports = reports.filter(
            Q(product__name__icontains=product_query)
            | Q(product__aliases__alias_name__icontains=product_query)
            | Q(product__tags__name__icontains=product_query)
        ).distinct()
    rows = _current_rows(reports, currency=currency, include_stale=include_stale)[:limit]

    return {
        **_branch_profile(branch, include_coverage=True),
        'currency': (currency or 'PGK').upper(),
        'product_query': product_query or None,
        'include_stale': bool(include_stale),
        'prices': rows,
        'price_count_returned': len(rows),
        'business_inventory': {
            'scope': 'business_wide',
            'branch_specific': False,
            'item_count': BusinessInventoryItem.objects.filter(business=branch.canonical_business).count(),
            'note': 'Business inventory is not branch-specific. Use the branch price rows above as branch-specific evidence.',
        },
        'business_url': _absolute_url(f'/business/{branch.canonical_business_id}/'),
    }


def search_businesses(query, *, limit=10):
    query = (query or '').strip()
    if not query:
        raise ValueError('Search query is required.')
    limit = max(1, min(int(limit), 50))
    businesses = Business.objects.filter(
        Q(name__icontains=query)
        | Q(details__icontains=query)
        | Q(aliases__alias_name__icontains=query)
        | Q(branches__name__icontains=query)
        | Q(branches__address__icontains=query)
    ).select_related('business_subcategory').distinct()[: max(limit * 3, 20)]

    ranked = []
    normalized = query.casefold()
    for business in businesses:
        branch_matches = list(
            business.branches.filter(
                Q(name__icontains=query) | Q(address__icontains=query)
            ).order_by('-is_main_branch', 'name')[:5]
        )
        coverage = _coverage(_business_reports(business))
        exact_name = business.name.casefold() == normalized
        name_prefix = business.name.casefold().startswith(normalized)
        branch_match = bool(branch_matches)
        sort_key = (
            0 if exact_name else 1 if name_prefix else 2 if branch_match else 3,
            0 if coverage['current_product_count'] else 1,
            -coverage['current_product_count'],
            business.name.casefold(),
        )
        ranked.append((sort_key, {
            'type': 'business',
            'id': business.pk,
            'name': business.name,
            'details': business.details or '',
            'subcategory': getattr(business.business_subcategory, 'name', None) if business.business_subcategory else None,
            'branch_count': business.branches.count(),
            'active_branch_count': business.branches.filter(is_active=True).count(),
            'inventory_item_count': business.inventory_items.count(),
            'price_coverage': coverage,
            'matching_branches': [
                _branch_profile(branch, include_coverage=False) for branch in branch_matches
            ],
            'url': _absolute_url(f'/business/{business.pk}/'),
            'next_tool_hint': 'Use get_business for current products and branch coverage, or get_branch with a matching branch ID for exact branch prices.',
        }))

    ranked.sort(key=lambda item: item[0])
    return [payload for _key, payload in ranked[:limit]]
