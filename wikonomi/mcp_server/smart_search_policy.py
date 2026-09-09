from decimal import Decimal

from .smart_search_services import search_products as base_search_products


def _price(row):
    value = row['current_price_summary'].get('min_price')
    return Decimal(value) if value is not None else Decimal('999999999')


def search_products(query, *, limit=10, **kwargs):
    """Apply shopper-facing ranking policy on top of identity candidate scoring."""
    requested_limit = max(1, min(int(limit), 50))
    expanded_limit = min(max(requested_limit * 5, 30), 50)
    payload = base_search_products(query, limit=expanded_limit, **kwargs)
    rows = payload['results']

    # Without a requested/inferred brand there is no reference brand, so a
    # branded result is a normal search match rather than an "alternative".
    if not payload['interpreted_query'].get('brand'):
        for row in rows:
            match = row.get('match', {})
            if match.get('relationship') == 'comparable_alternative':
                match['relationship'] = 'search_match'
                match['basis'] = 'name_or_alias'

        if payload['intent'].get('cheapest'):
            rows.sort(key=lambda row: (
                0 if row['current_price_summary'].get('comparable_store_count') else 1,
                -int(float(row.get('match', {}).get('score', 0)) * 10),
                _price(row),
                -float(row.get('match', {}).get('score', 0)),
                row.get('name', '').casefold(),
            ))
        else:
            current_intent = payload['intent'].get('current')
            rows.sort(key=lambda row: (
                0 if (not current_intent or row['current_price_summary'].get('comparable_store_count')) else 1,
                -float(row.get('match', {}).get('score', 0)),
                0 if row['current_price_summary'].get('comparable_store_count') else 1,
                row.get('name', '').casefold(),
            ))

    payload['results'] = rows[:requested_limit]
    payload['count'] = len(payload['results'])
    return payload
