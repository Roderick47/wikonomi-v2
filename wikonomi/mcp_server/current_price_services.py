from collections import Counter
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, Max, Min, Q

from core.models import Business, PriceReport, Product
from core.product_views import (
    COMPARISON_STALE_AFTER_DAYS,
    _freshness_metadata,
    _latest_store_price_ids,
    _store_key,
)
from guides.models import Guide


def _absolute_url(path):
    return f"{settings.WIKONOMI_MCP_PUBLIC_BASE_URL.rstrip('/')}{path}"


def _safe_average(values):
    if not values:
        return None
    return sum(values, Decimal('0')) / Decimal(len(values))


def _current_state(product, preferred_currency='PGK'):
    analysis_reports = PriceReport.objects.filter(
        product=product,
        marked_for_deletion=False,
    )
    latest_ids = _latest_store_price_ids(analysis_reports)
    latest_reports = list(
        analysis_reports.filter(id__in=latest_ids)
        .select_related('business', 'business_branch', 'user')
        .order_by('-observed_at', '-id')
    )

    currency_counts = Counter((report.currency or '').upper() for report in latest_reports if report.currency)
    if preferred_currency in currency_counts:
        comparison_currency = preferred_currency
    elif currency_counts:
        comparison_currency = currency_counts.most_common(1)[0][0]
    else:
        comparison_currency = preferred_currency

    chosen = [
        report for report in latest_reports
        if (report.currency or '').upper() == comparison_currency
    ]
    comparable = []
    latest_known_rows = []
    for report in chosen:
        freshness = _freshness_metadata(report.observed_at)
        row = {
            'id': report.pk,
            'price': str(report.price),
            'currency': report.currency,
            'business': report.get_business_display(),
            'business_id': report.business_id,
            'business_branch_id': report.business_branch_id,
            'observed_at': report.observed_at,
            'freshness': freshness['key'],
            'freshness_label': freshness['label'],
            'age_days': freshness['age_days'],
            'evidence_count': report.get_photo_count(),
            'url': _absolute_url(f'/price/{report.pk}/'),
        }
        latest_known_rows.append(row)
        if freshness['key'] != 'stale':
            comparable.append((report, row))

    comparable.sort(key=lambda pair: (pair[0].price, -pair[0].observed_at.timestamp(), pair[0].pk))
    latest_known_rows.sort(
        key=lambda row: (
            Decimal(row['price']),
            -(row['observed_at'].timestamp() if row['observed_at'] else 0),
            row['id'],
        )
    )

    prices = [report.price for report, _row in comparable]
    store_keys = {
        _store_key(report)
        for report in chosen
        if _store_key(report) is not None
    }
    comparable_store_keys = {
        _store_key(report)
        for report, _row in comparable
        if _store_key(report) is not None
    }

    return {
        'comparison_currency': comparison_currency,
        'stale_after_days': COMPARISON_STALE_AFTER_DAYS,
        'latest_known_store_count': len(store_keys),
        'comparable_store_count': len(comparable_store_keys),
        'stale_excluded_count': max(len(store_keys) - len(comparable_store_keys), 0),
        'min_price': min(prices) if prices else None,
        'max_price': max(prices) if prices else None,
        'average_price': _safe_average(prices),
        'best_report': comparable[0][1] if comparable else None,
        'latest_known_prices': latest_known_rows,
        'comparable_prices': [row for _report, row in comparable],
    }


def search_wikonomi(query, entity_types=None, limit=10):
    query = (query or '').strip()
    if not query:
        raise ValueError('Search query is required.')
    entity_types = entity_types or ['product', 'business', 'guide']
    limit = max(1, min(int(limit), 50))
    results = []

    if 'product' in entity_types:
        products = Product.objects.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(aliases__alias_name__icontains=query)
            | Q(tags__name__icontains=query)
        ).annotate(
            historical_price_count=Count(
                'price_reports',
                filter=Q(price_reports__marked_for_deletion=False),
                distinct=True,
            ),
        ).select_related('category').distinct()[:limit]

        for product in products:
            current = _current_state(product)
            results.append({
                'type': 'product',
                'id': product.pk,
                'name': product.name,
                'description': product.description,
                'category': product.category.name if product.category else None,
                'historical_price_count': product.historical_price_count,
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
            })

    if 'business' in entity_types:
        businesses = Business.objects.filter(
            Q(name__icontains=query)
            | Q(details__icontains=query)
            | Q(aliases__alias_name__icontains=query)
            | Q(branches__name__icontains=query)
        ).annotate(
            price_count=Count(
                'price_reports',
                filter=Q(price_reports__marked_for_deletion=False),
                distinct=True,
            ),
            branch_count=Count('branches', distinct=True),
        ).distinct()[:limit]
        results.extend({
            'type': 'business',
            'id': business.pk,
            'name': business.name,
            'details': business.details or '',
            'branch_count': business.branch_count,
            'price_count': business.price_count,
            'url': _absolute_url(f'/business/{business.pk}/'),
        } for business in businesses)

    if 'guide' in entity_types:
        guides = Guide.objects.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(current_version__steps__title__icontains=query)
            | Q(current_version__steps__instruction__icontains=query)
        ).filter(current_version__status='published').select_related(
            'organization', 'category', 'current_version'
        ).distinct()[:limit]
        results.extend({
            'type': 'guide',
            'id': guide.pk,
            'title': guide.title,
            'summary': guide.summary,
            'organization': guide.organization.name if guide.organization else None,
            'category': guide.category.name if guide.category else None,
            'url': _absolute_url(f'/guides/{guide.slug}/'),
        } for guide in guides)

    order = {'product': 0, 'business': 1, 'guide': 2}
    results.sort(key=lambda item: (order[item['type']], item.get('name') or item.get('title') or ''))
    return {'query': query, 'count': len(results), 'results': results[:limit * len(entity_types)]}


def get_product(product_id):
    product = Product.objects.select_related('category', 'created_by').prefetch_related('aliases', 'tags').filter(
        pk=product_id
    ).first()
    if not product:
        raise ValueError(f'Product {product_id} was not found.')

    historical_reports = product.price_reports.filter(marked_for_deletion=False)
    historical_stats = historical_reports.aggregate(
        count=Count('id'),
        min_price=Min('price'),
        max_price=Max('price'),
        average_price=Avg('price'),
        latest_observed=Max('observed_at'),
    )
    recent_reports = historical_reports.select_related(
        'business', 'business_branch', 'user'
    ).order_by('-observed_at', '-id')[:20]
    current = _current_state(product)

    return {
        'id': product.pk,
        'name': product.name,
        'description': product.description,
        'category': product.category.name if product.category else None,
        'aliases': [alias.alias_name for alias in product.aliases.filter(is_active=True)],
        'tags': list(product.tags.names()),
        'current_comparison': {
            'currency': current['comparison_currency'],
            'stale_after_days': current['stale_after_days'],
            'latest_known_store_count': current['latest_known_store_count'],
            'comparable_store_count': current['comparable_store_count'],
            'stale_excluded_count': current['stale_excluded_count'],
            'min_price': str(current['min_price']) if current['min_price'] is not None else None,
            'max_price': str(current['max_price']) if current['max_price'] is not None else None,
            'average_price': str(current['average_price']) if current['average_price'] is not None else None,
            'best_price': current['best_report'],
            'latest_known_prices': current['latest_known_prices'],
        },
        'historical_statistics': {
            'count': historical_stats['count'],
            'min_price': str(historical_stats['min_price']) if historical_stats['min_price'] is not None else None,
            'max_price': str(historical_stats['max_price']) if historical_stats['max_price'] is not None else None,
            'average_price': str(historical_stats['average_price']) if historical_stats['average_price'] is not None else None,
            'latest_observed': historical_stats['latest_observed'],
        },
        'recent_prices': [{
            'id': report.pk,
            'price': str(report.price),
            'currency': report.currency,
            'business': report.get_business_display(),
            'observed_at': report.observed_at,
            'evidence_count': report.get_photo_count(),
            'url': _absolute_url(f'/price/{report.pk}/'),
        } for report in recent_reports],
        'url': _absolute_url(f'/product/{product.pk}/'),
    }


def install_service_upgrades():
    # Keep tool registration stable while upgrading the read semantics in one place.
    from . import services

    services.search_wikonomi = search_wikonomi
    services.get_product = get_product
