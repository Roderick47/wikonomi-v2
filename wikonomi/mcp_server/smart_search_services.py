import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from django.db.models import Q

from catalog.models import ProductIdentity
from catalog.services import normalize_barcode, normalize_text, normalize_unit, parse_product_identity
from core.models import Product

from .current_price_services import _absolute_url, _current_state, search_wikonomi as basic_search_wikonomi


SHOPPING_INTENT_WORDS = {
    'cheap', 'cheaper', 'cheapest', 'lowest', 'best', 'value', 'price', 'prices',
    'pricing', 'compare', 'comparison', 'current', 'currently', 'fresh', 'available',
    'deal', 'deals', 'cost', 'costs', 'buy', 'buying', 'find', 'show', 'me', 'for',
}
CHEAP_INTENT_WORDS = {'cheap', 'cheaper', 'cheapest', 'lowest', 'deal', 'deals', 'cost', 'costs'}
VALUE_INTENT_WORDS = {'value', 'best'}
CURRENT_INTENT_WORDS = {'current', 'currently', 'fresh', 'available'}


def _decimal_or_none(value):
    if value in (None, ''):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('package_quantity must be a valid number.') from exc
    if result <= 0:
        raise ValueError('package_quantity must be greater than zero.')
    return result


def _base_measure(quantity, unit):
    if quantity is None or not unit:
        return None
    quantity = Decimal(str(quantity))
    unit = normalize_unit(unit) or unit
    if unit == 'kg':
        return ('mass', quantity * Decimal('1000'))
    if unit == 'g':
        return ('mass', quantity)
    if unit == 'l':
        return ('volume', quantity * Decimal('1000'))
    if unit == 'ml':
        return ('volume', quantity)
    if unit == 'm':
        return ('length', quantity * Decimal('100'))
    if unit == 'cm':
        return ('length', quantity)
    if unit == 'each':
        return ('each', quantity)
    return (unit, quantity)


def _intent(query):
    tokens = normalize_text(query).split()
    token_set = set(tokens)
    return {
        'cheapest': bool(token_set & CHEAP_INTENT_WORDS),
        'value': bool(token_set & VALUE_INTENT_WORDS),
        'current': bool(token_set & CURRENT_INTENT_WORDS),
    }


def _semantic_query(query):
    # Preserve size/barcode tokens while removing conversational shopping filler.
    tokens = normalize_text(query).split()
    kept = [token for token in tokens if token not in SHOPPING_INTENT_WORDS]
    return ' '.join(kept) or normalize_text(query)


def _infer_brand(query):
    normalized = normalize_text(query)
    if not normalized:
        return ''
    brands = ProductIdentity.objects.exclude(brand='').values_list('brand', flat=True).distinct()[:200]
    matches = []
    for brand in brands:
        normalized_brand = normalize_text(brand)
        if normalized_brand and re.search(rf'(^|\s){re.escape(normalized_brand)}(?=\s|$)', normalized):
            matches.append((len(normalized_brand), brand))
    return max(matches, default=(0, ''))[1]


def _identity_data(product):
    try:
        stored = product.identity
    except ProductIdentity.DoesNotExist:
        stored = None

    brand = stored.brand if stored else ''
    variant = stored.variant if stored else ''
    barcode = stored.barcode if stored else ''
    parsed = parse_product_identity(
        product.name,
        brand=brand,
        variant=variant,
        barcode=barcode,
        unit=stored.package_unit if stored else '',
    )
    quantity = stored.package_quantity if stored and stored.package_quantity is not None else parsed.package_quantity
    package_unit = stored.package_unit if stored and stored.package_unit else parsed.package_unit
    pack_count = stored.pack_count if stored and stored.pack_count else parsed.pack_count
    normalized_code = stored.normalized_barcode if stored and stored.normalized_barcode else parsed.normalized_barcode
    return {
        'brand': brand or None,
        'normalized_brand': normalize_text(brand),
        'variant': variant or None,
        'normalized_variant': normalize_text(variant),
        'base_name': parsed.base_name,
        'package_quantity': quantity,
        'package_unit': package_unit or None,
        'pack_count': pack_count,
        'barcode': barcode or None,
        'normalized_barcode': normalized_code or None,
        'identity_signature': stored.identity_signature if stored and stored.identity_signature else parsed.identity_signature or None,
        'source': stored.source if stored else ProductIdentity.Source.INFERRED,
        'confidence': str(stored.confidence) if stored and stored.confidence is not None else None,
    }


def _query_identity(query, *, brand='', variant='', barcode='', package_quantity=None, package_unit='', pack_count=None):
    semantic = _semantic_query(query)
    inferred_brand = brand or _infer_brand(semantic)
    parsed = parse_product_identity(
        semantic,
        brand=inferred_brand,
        variant=variant,
        barcode=barcode,
        unit=package_unit,
    )
    quantity = _decimal_or_none(package_quantity)
    normalized_package_unit = normalize_unit(package_unit) if package_unit else ''
    if package_unit and not normalized_package_unit:
        raise ValueError(f'Unsupported package unit: {package_unit}.')
    if quantity is None:
        quantity = parsed.package_quantity
    if not normalized_package_unit:
        normalized_package_unit = parsed.package_unit
    count = int(pack_count) if pack_count is not None else parsed.pack_count
    if count is not None and count <= 0:
        raise ValueError('pack_count must be greater than zero.')
    return {
        'semantic_query': semantic,
        'base_name': parsed.base_name,
        'brand': inferred_brand,
        'normalized_brand': normalize_text(inferred_brand),
        'variant': variant or parsed.variant,
        'normalized_variant': normalize_text(variant or parsed.variant),
        'barcode': barcode or (query if normalize_barcode(query).isdigit() and len(normalize_barcode(query)) >= 8 else ''),
        'normalized_barcode': normalize_barcode(barcode or (query if normalize_barcode(query).isdigit() and len(normalize_barcode(query)) >= 8 else '')),
        'package_quantity': quantity,
        'package_unit': normalized_package_unit,
        'pack_count': count,
    }


def _text_score(query_base, candidate_base, product_name, aliases):
    query_base = normalize_text(query_base)
    candidate_base = normalize_text(candidate_base)
    if not query_base:
        return 0.5
    normalized_name = normalize_text(product_name)
    if query_base == normalized_name or query_base == candidate_base:
        return 1.0
    alias_names = [normalize_text(alias.alias_name) for alias in aliases if alias.is_active]
    if query_base in alias_names:
        return 1.0

    query_tokens = set(query_base.split())
    candidate_tokens = set(candidate_base.split()) | set(normalized_name.split())
    overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
    sequence = max(
        SequenceMatcher(None, query_base, candidate_base).ratio() if candidate_base else 0,
        SequenceMatcher(None, query_base, normalized_name).ratio(),
    )
    return max(overlap, sequence)


def _match_product(product, query_identity):
    identity = _identity_data(product)
    aliases = list(product.aliases.all())
    query_code = query_identity['normalized_barcode']
    if query_code and identity['normalized_barcode'] == query_code:
        return 1.0, 'barcode', 'exact_product', ['barcode'], identity

    score = _text_score(query_identity['base_name'], identity['base_name'], product.name, aliases)
    matched_fields = []
    if score >= 0.99:
        matched_fields.append('name')

    query_brand = query_identity['normalized_brand']
    candidate_brand = identity['normalized_brand']
    brand_same = bool(query_brand and candidate_brand and query_brand == candidate_brand)
    brand_conflict = bool(query_brand and candidate_brand and query_brand != candidate_brand)
    if brand_same:
        score = min(1.0, score + 0.08)
        matched_fields.append('brand')

    query_variant = query_identity['normalized_variant']
    candidate_variant = identity['normalized_variant']
    if query_variant and candidate_variant and query_variant == candidate_variant:
        score = min(1.0, score + 0.04)
        matched_fields.append('variant')

    query_measure = _base_measure(query_identity['package_quantity'], query_identity['package_unit'])
    candidate_measure = _base_measure(identity['package_quantity'], identity['package_unit'])
    package_same = False
    package_dimension_same = False
    if query_measure and candidate_measure:
        package_dimension_same = query_measure[0] == candidate_measure[0]
        package_same = package_dimension_same and query_measure[1] == candidate_measure[1]
        query_pack = query_identity['pack_count'] or 1
        candidate_pack = identity['pack_count'] or 1
        package_same = package_same and query_pack == candidate_pack
        if package_same:
            score = min(1.0, score + 0.08)
            matched_fields.append('package')
        elif package_dimension_same:
            score = max(0.0, score - 0.03)

    if score >= 0.98 and not brand_conflict and (not query_measure or package_same):
        relationship = 'exact_product'
        basis = 'structured_identity' if matched_fields else 'name'
    elif brand_same and query_measure and package_dimension_same and not package_same:
        relationship = 'same_brand_different_pack'
        basis = 'compatible_identity'
    elif score >= 0.6 and (brand_conflict or (not query_brand and candidate_brand)):
        relationship = 'comparable_alternative'
        basis = 'compatible_name'
    else:
        relationship = 'search_match'
        basis = 'name_or_alias'

    return score, basis, relationship, matched_fields, identity


def _candidate_products(query_identity, category_id=None, limit=10):
    query_code = query_identity['normalized_barcode']
    if query_code:
        exact = Product.objects.select_related('category', 'identity').prefetch_related('aliases').filter(
            identity__normalized_barcode=query_code
        )
        if exact.exists():
            return list(exact[: max(limit, 5)])

    base = query_identity['base_name'] or query_identity['semantic_query']
    tokens = [token for token in normalize_text(base).split() if len(token) >= 2]
    query_filter = Q()
    if base:
        query_filter |= Q(name__icontains=base) | Q(aliases__alias_name__icontains=base)
    for token in tokens[:6]:
        query_filter |= Q(name__icontains=token) | Q(aliases__alias_name__icontains=token) | Q(tags__name__icontains=token)
    if query_identity['brand']:
        query_filter |= Q(identity__brand__iexact=query_identity['brand'])
    if not query_filter:
        query_filter = Q(pk__isnull=False)

    queryset = Product.objects.select_related('category', 'identity').prefetch_related('aliases').filter(query_filter).distinct()
    if category_id is not None:
        queryset = queryset.filter(category_id=category_id)
    pool_size = min(max(int(limit) * 6, 30), 100)
    return list(queryset[:pool_size])


def search_products(
    query,
    *,
    limit=10,
    brand='',
    variant='',
    barcode='',
    package_quantity=None,
    package_unit='',
    pack_count=None,
    category_id=None,
    include_alternatives=True,
    current_only=False,
):
    query = (query or '').strip()
    if not query:
        raise ValueError('Search query is required.')
    limit = max(1, min(int(limit), 50))
    query_identity = _query_identity(
        query,
        brand=brand,
        variant=variant,
        barcode=barcode,
        package_quantity=package_quantity,
        package_unit=package_unit,
        pack_count=pack_count,
    )
    intent = _intent(query)
    candidates = _candidate_products(query_identity, category_id=category_id, limit=limit)
    ranked = []

    for product in candidates:
        score, basis, relationship, matched_fields, identity = _match_product(product, query_identity)
        if score < 0.42 and basis != 'barcode':
            continue
        if not include_alternatives and relationship in {'comparable_alternative'}:
            continue

        current = _current_state(product)
        if current_only and current['comparable_store_count'] == 0:
            continue
        min_price = current['min_price']
        availability_rank = 0 if current['comparable_store_count'] else 1
        relationship_rank = {
            'exact_product': 0,
            'same_brand_different_pack': 1,
            'search_match': 2,
            'comparable_alternative': 3,
        }.get(relationship, 4)
        relevance_bucket = int(score * 10)
        if intent['cheapest']:
            sort_key = (availability_rank, relationship_rank, -relevance_bucket, min_price if min_price is not None else Decimal('999999999'), -score, product.name.casefold())
        else:
            sort_key = (availability_rank if intent['current'] else 0, relationship_rank, -score, availability_rank, product.name.casefold())

        ranked.append((sort_key, {
            'type': 'product',
            'id': product.pk,
            'name': product.name,
            'description': product.description,
            'category': product.category.name if product.category else None,
            'structured_identity': {
                'brand': identity['brand'],
                'variant': identity['variant'],
                'package_quantity': str(identity['package_quantity']) if identity['package_quantity'] is not None else None,
                'package_unit': identity['package_unit'],
                'pack_count': identity['pack_count'],
                'barcode': identity['barcode'],
                'source': identity['source'],
                'confidence': identity['confidence'],
            },
            'match': {
                'score': round(float(score), 4),
                'basis': basis,
                'relationship': relationship,
                'matched_fields': matched_fields,
            },
            'current_price_summary': {
                'currency': current['comparison_currency'],
                'comparable_store_count': current['comparable_store_count'],
                'latest_known_store_count': current['latest_known_store_count'],
                'stale_excluded_count': current['stale_excluded_count'],
                'min_price': str(current['min_price']) if current['min_price'] is not None else None,
                'max_price': str(current['max_price']) if current['max_price'] is not None else None,
                'average_price': str(current['average_price']) if current['average_price'] is not None else None,
                'best_price': current['best_report'],
                'stale_after_days': current['stale_after_days'],
            },
            'url': _absolute_url(f'/product/{product.pk}/'),
            'value_comparison_url': _absolute_url(f'/product/{product.pk}/value/'),
        }))

    ranked.sort(key=lambda item: item[0])
    results = [item for _key, item in ranked[:limit]]
    return {
        'query': query,
        'interpreted_query': {
            'semantic_query': query_identity['semantic_query'],
            'brand': query_identity['brand'] or None,
            'variant': query_identity['variant'] or None,
            'barcode': query_identity['barcode'] or None,
            'package_quantity': str(query_identity['package_quantity']) if query_identity['package_quantity'] is not None else None,
            'package_unit': query_identity['package_unit'] or None,
            'pack_count': query_identity['pack_count'],
            'category_id': category_id,
        },
        'intent': intent,
        'current_only': bool(current_only),
        'include_alternatives': bool(include_alternatives),
        'count': len(results),
        'results': results,
        'next_tool_hint': 'Use compare_product_value for unit-value ranking or compare_current_prices for exact store-by-store comparison.' if results else None,
    }


def search_wikonomi(query, entity_types=None, limit=10):
    entity_types = entity_types or ['product', 'business', 'guide']
    results = []
    if 'product' in entity_types:
        results.extend(search_products(query, limit=limit)['results'])
    other_types = [entity_type for entity_type in entity_types if entity_type in {'business', 'guide'}]
    if other_types:
        results.extend(basic_search_wikonomi(query, other_types, limit)['results'])
    order = {'product': 0, 'business': 1, 'guide': 2}
    results.sort(key=lambda item: (order.get(item['type'], 9), item.get('match', {}).get('relationship') != 'exact_product', item.get('name') or item.get('title') or ''))
    return {'query': query, 'count': len(results), 'results': results[: limit * len(entity_types)]}


def install_smart_search_upgrades():
    from . import services
    services.search_wikonomi = search_wikonomi
