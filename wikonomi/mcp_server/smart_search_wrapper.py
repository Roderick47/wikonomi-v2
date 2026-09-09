from .current_price_services import search_wikonomi as basic_search_wikonomi
from .smart_search_policy import search_products


def search_wikonomi(query, entity_types=None, limit=10):
    entity_types = entity_types or ['product', 'business', 'guide']
    results = []

    # Product results are already relevance/freshness/value-intent ranked. Keep
    # that order instead of alphabetically re-sorting it afterward.
    if 'product' in entity_types:
        results.extend(search_products(query, limit=limit)['results'])

    other_types = [entity_type for entity_type in entity_types if entity_type in {'business', 'guide'}]
    if other_types:
        results.extend(basic_search_wikonomi(query, other_types, limit)['results'])

    return {
        'query': query,
        'count': len(results),
        'results': results[: limit * len(entity_types)],
    }


def install_smart_search_upgrades():
    from . import services
    services.search_wikonomi = search_wikonomi
