from .business_search_policy import search_businesses
from .current_price_services import search_wikonomi as basic_search_wikonomi
from .smart_search_policy import search_products


def search_wikonomi(query, entity_types=None, limit=10):
    entity_types = entity_types or ['product', 'business', 'guide']
    results = []

    # Product results are already relevance/freshness/value-intent ranked. Keep
    # that order instead of alphabetically re-sorting it afterward.
    if 'product' in entity_types:
        results.extend(search_products(query, limit=limit)['results'])

    # Business search can resolve by business identity, branch name/address,
    # fresh product-price evidence, or business-wide imported catalogue data.
    if 'business' in entity_types:
        results.extend(search_businesses(query, limit=limit))

    # Guide search remains on the established published-guide path.
    if 'guide' in entity_types:
        results.extend(basic_search_wikonomi(query, ['guide'], limit)['results'])

    return {
        'query': query,
        'count': len(results),
        'results': results[: limit * len(entity_types)],
    }


def install_smart_search_upgrades():
    from . import services
    services.search_wikonomi = search_wikonomi
