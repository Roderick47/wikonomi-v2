from django.db.models import Q

from catalog.services import normalize_text
from core.models import Business

from .business_intelligence_services import (
    _branch_profile,
    _business_reports,
    _coverage,
    _current_rows,
)
from .current_price_services import _absolute_url


BUSINESS_QUERY_STOPWORDS = {
    'a', 'an', 'and', 'are', 'at', 'business', 'businesses', 'branch', 'branches',
    'current', 'currently', 'data', 'do', 'does', 'find', 'for', 'has', 'have',
    'in', 'is', 'me', 'of', 'price', 'prices', 'recent', 'show', 'store', 'stores',
    'supermarket', 'supermarkets', 'the', 'what', 'which', 'with',
}


def _query_tokens(query):
    tokens = [token for token in normalize_text(query).split() if len(token) >= 2]
    meaningful = [token for token in tokens if token not in BUSINESS_QUERY_STOPWORDS]
    return meaningful or tokens


def _or_lookup(tokens, lookups):
    query_filter = Q()
    for token in tokens:
        for lookup in lookups:
            query_filter |= Q(**{lookup: token})
    return query_filter


def search_businesses(query, *, limit=10):
    """Search businesses by identity, branch, current price data, or imported catalog data."""
    query = (query or '').strip()
    if not query:
        raise ValueError('Search query is required.')
    limit = max(1, min(int(limit), 50))
    tokens = _query_tokens(query)

    candidate_filter = _or_lookup(tokens, [
        'name__icontains',
        'details__icontains',
        'aliases__alias_name__icontains',
        'branches__name__icontains',
        'branches__address__icontains',
        'price_reports__product__name__icontains',
        'price_reports__product__aliases__alias_name__icontains',
        'branches__price_reports__product__name__icontains',
        'branches__price_reports__product__aliases__alias_name__icontains',
        'inventory_items__product__name__icontains',
        'inventory_items__brand__icontains',
        'inventory_items__barcode__icontains',
    ])
    businesses = Business.objects.filter(candidate_filter).select_related('business_subcategory').distinct()[: max(limit * 4, 30)]

    normalized = normalize_text(query)
    ranked = []
    for business in businesses:
        all_reports = _business_reports(business)
        product_filter = _or_lookup(tokens, [
            'product__name__icontains',
            'product__aliases__alias_name__icontains',
            'product__tags__name__icontains',
        ])
        matching_reports = all_reports.filter(product_filter).distinct()
        matching_current_rows = _current_rows(matching_reports, currency='PGK', include_stale=False)
        matching_current_product_ids = {row['product_id'] for row in matching_current_rows}

        inventory_filter = _or_lookup(tokens, [
            'product__name__icontains',
            'brand__icontains',
            'barcode__icontains',
        ])
        inventory_matches = list(
            business.inventory_items.filter(inventory_filter)
            .select_related('product')
            .order_by('product__name')[:5]
        )

        branch_filter = _or_lookup(tokens, ['name__icontains', 'address__icontains'])
        direct_branch_matches = list(
            business.branches.filter(branch_filter).order_by('-is_main_branch', 'name')[:5]
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
        normalized_name = normalize_text(business.name)
        exact_name = normalized_name == normalized
        name_prefix = normalized_name.startswith(normalized)
        identity_text = normalize_text(' '.join(
            [business.name]
            + [f'{branch.name} {branch.address or ""}' for branch in direct_branch_matches]
        ))
        identity_words = set(identity_text.split())
        identity_token_hits = sum(1 for token in tokens if token in identity_words)
        has_current_product_match = bool(matching_current_product_ids)
        has_inventory_match = bool(inventory_matches)
        sort_key = (
            0 if exact_name else 1 if name_prefix else 2 if identity_token_hits else 3 if has_current_product_match else 4 if has_inventory_match else 5,
            -identity_token_hits,
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
            'interpreted_query_tokens': tokens,
            'identity_token_hits': identity_token_hits,
            'url': _absolute_url(f'/business/{business.pk}/'),
            'next_tool_hint': 'Use get_business for current products and coverage, or get_branch with a matching branch ID for exact branch prices.',
        }))

    ranked.sort(key=lambda item: item[0])
    return [payload for _key, payload in ranked[:limit]]
