from django.db.models import Q

from core.models import Business

from .business_intelligence_services import (
    _branch_profile,
    _business_reports,
    _coverage,
    _current_rows,
)
from .current_price_services import _absolute_url


def search_businesses(query, *, limit=10):
    """Search businesses by identity, branch, current price data, or imported catalog data."""
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
        | Q(price_reports__product__name__icontains=query)
        | Q(price_reports__product__aliases__alias_name__icontains=query)
        | Q(branches__price_reports__product__name__icontains=query)
        | Q(branches__price_reports__product__aliases__alias_name__icontains=query)
        | Q(inventory_items__product__name__icontains=query)
        | Q(inventory_items__brand__icontains=query)
        | Q(inventory_items__barcode__icontains=query)
    ).select_related('business_subcategory').distinct()[: max(limit * 4, 30)]

    normalized = query.casefold()
    ranked = []
    for business in businesses:
        all_reports = _business_reports(business)
        matching_reports = all_reports.filter(
            Q(product__name__icontains=query)
            | Q(product__aliases__alias_name__icontains=query)
            | Q(product__tags__name__icontains=query)
        ).distinct()
        matching_current_rows = _current_rows(matching_reports, currency='PGK', include_stale=False)
        matching_current_product_ids = {row['product_id'] for row in matching_current_rows}

        inventory_matches = list(
            business.inventory_items.filter(
                Q(product__name__icontains=query)
                | Q(brand__icontains=query)
                | Q(barcode__icontains=query)
            ).select_related('product').order_by('product__name')[:5]
        )

        direct_branch_matches = list(
            business.branches.filter(
                Q(name__icontains=query) | Q(address__icontains=query)
            ).order_by('-is_main_branch', 'name')[:5]
        )
        data_branch_ids = {
            row['branch_id'] for row in matching_current_rows if row['branch_id'] is not None
        }
        data_branches = list(
            business.branches.filter(pk__in=data_branch_ids).order_by('-is_main_branch', 'name')[:5]
        )
        branch_by_id = {branch.pk: branch for branch in direct_branch_matches}
        for branch in data_branches:
            branch_by_id.setdefault(branch.pk, branch)
        branch_matches = list(branch_by_id.values())[:5]

        coverage = _coverage(all_reports)
        exact_name = business.name.casefold() == normalized
        name_prefix = business.name.casefold().startswith(normalized)
        direct_branch_match = bool(direct_branch_matches)
        has_current_product_match = bool(matching_current_product_ids)
        has_inventory_match = bool(inventory_matches)
        sort_key = (
            0 if exact_name else 1 if name_prefix else 2 if direct_branch_match else 3 if has_current_product_match else 4 if has_inventory_match else 5,
            0 if has_current_product_match else 1,
            -len(matching_current_product_ids),
            0 if coverage['current_product_count'] else 1,
            -coverage['current_product_count'],
            business.name.casefold(),
        )

        matching_products = []
        seen_products = set()
        for row in matching_current_rows:
            if row['product_id'] in seen_products:
                continue
            seen_products.add(row['product_id'])
            matching_products.append({
                'product_id': row['product_id'],
                'product_name': row['product_name'],
                'best_known_price_at_this_business': row['price'],
                'currency': row['currency'],
                'branch_id': row['branch_id'],
                'branch_name': row['branch_name'],
                'observed_at': row['observed_at'],
                'freshness': row['freshness'],
            })
            if len(matching_products) >= 5:
                break

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
            'matching_current_product_count': len(matching_current_product_ids),
            'matching_current_products': matching_products,
            'matching_inventory_products': [{
                'product_id': item.product_id,
                'product_name': item.product.name,
                'brand': item.brand or None,
                'barcode': item.barcode or None,
                'stock_quantity': str(item.stock_quantity) if item.stock_quantity is not None else None,
                'scope': 'business_wide',
            } for item in inventory_matches],
            'matching_branches': [
                _branch_profile(branch, include_coverage=False) for branch in branch_matches
            ],
            'url': _absolute_url(f'/business/{business.pk}/'),
            'next_tool_hint': 'Use get_business for current products and coverage, or get_branch with a matching branch ID for exact branch prices.',
        }))

    ranked.sort(key=lambda item: item[0])
    return [payload for _key, payload in ranked[:limit]]
