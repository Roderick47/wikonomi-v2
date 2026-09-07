from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Avg, Count, Max, Min, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Business, Product, ProductAlias, PriceLike, PriceReport, PriceReportPhoto, ProductWatchlist
from .utils import annotate_with_distance


def _product_family_ids(product):
    """Return product IDs that should be analysed together for a product page."""
    alias_names = list(ProductAlias.objects.filter(
        canonical_product=product,
        is_active=True,
    ).values_list('alias_name', flat=True))

    name_variants = {product.name}
    name_variants.update(name for name in alias_names if name)

    variant_products_qs = Product.objects.filter(name__in=list(name_variants))
    variant_products_qs = variant_products_qs | Product.objects.filter(id=product.id)
    return list(variant_products_qs.values_list('id', flat=True).distinct())


def _parse_location(request):
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    try:
        if lat not in (None, '') and lng not in (None, ''):
            return float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None
    return None, None


def _with_user_card_state(request, reports):
    """Attach like state expected by the shared price card partial."""
    reports = list(reports)
    if request.user.is_authenticated and reports:
        liked_ids = set(PriceLike.objects.filter(
            user=request.user,
            price_report_id__in=[report.id for report in reports],
        ).values_list('price_report_id', flat=True))
        for report in reports:
            report.is_liked_by_user = report.id in liked_ids
    return reports


def _store_key(report):
    """Return the safest store/location identity available for a price report."""
    if report.business_branch_id:
        return ('branch', report.business_branch_id)
    if report.business_id:
        return ('business', report.business_id)
    return None


def _latest_store_price_ids(reports):
    """
    Return one current report per store/location and currency.

    Historical observations remain in the product history, but only the latest
    valid observation from a store is allowed to influence current comparison
    cards, ranges, averages, savings, and nearby rankings.
    """
    candidates = reports.filter(
        marked_for_deletion=False,
        price__gt=0,
    ).exclude(currency='').filter(
        Q(business__isnull=False) | Q(business_branch__isnull=False)
    ).only(
        'id', 'business_id', 'business_branch_id', 'currency', 'observed_at'
    ).order_by(
        'currency', 'business_branch_id', 'business_id', '-observed_at', '-id'
    )

    seen = set()
    latest_ids = []
    for report in candidates:
        store_key = _store_key(report)
        if store_key is None:
            continue
        comparison_key = ((report.currency or '').upper(), store_key)
        if comparison_key in seen:
            continue
        seen.add(comparison_key)
        latest_ids.append(report.id)
    return latest_ids


def _freshness_metadata(observed_at, now=None):
    """Classify an observation by how useful it is for a current-price decision."""
    if not observed_at:
        return {'key': 'stale', 'label': 'Stale', 'age_days': None}

    now = now or timezone.now()
    age_days = max((now - observed_at).days, 0)
    if age_days <= 7:
        key, label = 'fresh', 'Fresh'
    elif age_days <= 30:
        key, label = 'recent', 'Recent'
    elif age_days <= 90:
        key, label = 'old', 'Old'
    else:
        key, label = 'stale', 'Stale'
    return {'key': key, 'label': label, 'age_days': age_days}


def _decorate_comparison_reports(reports, cheapest_report=None, distance_by_id=None):
    """Add presentation-only comparison metadata to report instances."""
    now = timezone.now()
    distance_by_id = distance_by_id or {}
    reports = list(reports)
    for report in reports:
        freshness = _freshness_metadata(report.observed_at, now=now)
        report.freshness_key = freshness['key']
        report.freshness_label = freshness['label']
        report.freshness_age_days = freshness['age_days']
        report.distance_km = distance_by_id.get(report.id)
        report.price_gap = None
        report.price_gap_percent = None
        if (
            cheapest_report
            and report.currency == cheapest_report.currency
            and report.price > cheapest_report.price
            and cheapest_report.price > 0
        ):
            report.price_gap = report.price - cheapest_report.price
            report.price_gap_percent = (report.price_gap / cheapest_report.price) * 100
    return reports


def business_list(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'popular')

    businesses = Business.objects.annotate(
        report_count=Count('price_reports', distinct=True),
        product_count=Count('price_reports__product', distinct=True),
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings', distinct=True),
        latest_observed=Max('price_reports__observed_at'),
    )

    if query:
        businesses = businesses.filter(
            Q(name__icontains=query)
            | Q(details__icontains=query)
            | Q(branches__name__icontains=query)
            | Q(branches__address__icontains=query)
            | Q(price_reports__product__name__icontains=query)
        ).distinct()

    if sort == 'name':
        businesses = businesses.order_by('name')
    elif sort == 'recent':
        businesses = businesses.order_by('-latest_observed', 'name')
    elif sort == 'rated':
        businesses = businesses.order_by('-avg_rating', '-rating_count', 'name')
    else:
        businesses = businesses.order_by('-report_count', 'name')

    paginator = Paginator(businesses, 30)
    page_number = request.GET.get('page', 1)
    try:
        businesses_page = paginator.page(page_number)
    except PageNotAnInteger:
        businesses_page = paginator.page(1)
    except EmptyPage:
        businesses_page = paginator.page(paginator.num_pages or 1)

    latest_reports = PriceReport.objects.filter(
        business_id__in=[business.id for business in businesses_page.object_list]
    ).select_related('product', 'business_branch').order_by('business_id', '-observed_at')
    latest_by_business = {}
    for report in latest_reports:
        latest_by_business.setdefault(report.business_id, report)

    for business in businesses_page.object_list:
        business.latest_report = latest_by_business.get(business.id)

    return render(request, 'business_list.html', {
        'businesses_page': businesses_page,
        'search_query': query,
        'current_sort': sort,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.prefetch_related('tags', 'aliases'), pk=pk)
    product_ids = _product_family_ids(product)

    analysis_reports = PriceReport.objects.filter(
        product_id__in=product_ids,
        marked_for_deletion=False,
    )
    base_reports = analysis_reports.select_related(
        'product',
        'business',
        'business_branch',
        'user',
        'user__profile',
    ).prefetch_related('product__tags', 'likes').annotate(
        average_rating=Avg('ratings__rating'),
        rating_count=Count('ratings'),
    ).order_by('-observed_at')

    current_report_ids = _latest_store_price_ids(analysis_reports)
    current_reports = base_reports.filter(id__in=current_report_ids)
    current_reports_list = list(current_reports)

    currency_counts = {}
    for report in current_reports_list:
        currency_counts[report.currency] = currency_counts.get(report.currency, 0) + 1
    if 'PGK' in currency_counts:
        comparison_currency = 'PGK'
    elif currency_counts:
        comparison_currency = max(currency_counts, key=currency_counts.get)
    else:
        comparison_currency = 'PGK'

    user_lat, user_lng = _parse_location(request)
    sort = request.GET.get('sort', 'recent')
    query = request.GET.get('q', '').strip()
    reports = base_reports
    if query:
        reports = reports.filter(
            Q(business__name__icontains=query)
            | Q(business_branch__name__icontains=query)
            | Q(notes__icontains=query)
            | Q(currency__icontains=query)
        )

    nearby_reports = PriceReport.objects.none()
    distance_by_id = {}
    if user_lat is not None and user_lng is not None:
        nearby_reports = annotate_with_distance(
            current_reports.filter(latitude__isnull=False, longitude__isnull=False),
            user_lat,
            user_lng,
            radius_hexes=4,
        )
        distance_by_id = {
            report.id: report.distance_km
            for report in nearby_reports
        }
        if sort == 'nearest':
            reports = annotate_with_distance(
                reports.filter(latitude__isnull=False, longitude__isnull=False),
                user_lat,
                user_lng,
                radius_hexes=4,
            )

    if sort == 'price_asc':
        reports = reports.order_by('price', '-observed_at')
    elif sort == 'price_desc':
        reports = reports.order_by('-price', '-observed_at')
    elif sort == 'oldest':
        reports = reports.order_by('observed_at')
    elif sort != 'nearest':
        reports = reports.order_by('-observed_at')

    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page', 1)
    try:
        reports_page = paginator.page(page_number)
    except PageNotAnInteger:
        reports_page = paginator.page(1)
    except EmptyPage:
        reports_page = paginator.page(paginator.num_pages or 1)

    reports_page.object_list = _with_user_card_state(request, reports_page.object_list)

    currency_stats = list(current_reports.values('currency').annotate(
        report_count=Count('id'),
        min_price=Min('price'),
        max_price=Max('price'),
        avg_price=Avg('price'),
        latest_observed=Max('observed_at'),
    ).order_by('-report_count', 'currency'))

    comparison_qs = current_reports.filter(currency=comparison_currency).order_by('price', '-observed_at')
    comparison_reports = list(comparison_qs)
    cheapest_report = comparison_reports[0] if comparison_reports else None
    most_expensive_report = comparison_reports[-1] if comparison_reports else None
    comparison_reports = _decorate_comparison_reports(
        comparison_reports,
        cheapest_report=cheapest_report,
        distance_by_id=distance_by_id,
    )

    comparison_store_keys = {
        _store_key(report)
        for report in current_reports_list
        if _store_key(report) is not None
    }
    comparison_store_count = len(comparison_store_keys)

    comparison_savings_amount = None
    comparison_savings_percent = None
    if (
        cheapest_report
        and most_expensive_report
        and cheapest_report.id != most_expensive_report.id
        and most_expensive_report.price > cheapest_report.price
    ):
        comparison_savings_amount = most_expensive_report.price - cheapest_report.price
        comparison_savings_percent = (comparison_savings_amount / most_expensive_report.price) * 100

    nearest_reports = []
    nearby_cheapest_report = None
    nearby_most_expensive_report = None

    if user_lat is not None and user_lng is not None:
        nearest_reports = _with_user_card_state(request, nearby_reports[:5])
        nearby_currency_reports = nearby_reports.filter(currency=comparison_currency)
        nearby_cheapest_report = nearby_currency_reports.order_by('price', 'distance_km').first()
        nearby_most_expensive_report = nearby_currency_reports.order_by('-price', 'distance_km').first()

    if nearby_cheapest_report is None:
        nearby_cheapest_report = cheapest_report
    if nearby_most_expensive_report is None:
        nearby_most_expensive_report = most_expensive_report

    reports_with_location = current_reports.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    ).select_related('business')[:100]

    product_photos = PriceReportPhoto.objects.filter(
        price_report__product_id__in=product_ids,
        price_report__marked_for_deletion=False,
    ).select_related('price_report', 'price_report__business').order_by('-price_report__observed_at')[:12]
    if not product_photos and product.image:
        product_photos = []

    is_watching = False
    if request.user.is_authenticated:
        is_watching = ProductWatchlist.objects.filter(user=request.user, product=product).exists()

    context = {
        'product': product,
        'aliases': ProductAlias.objects.filter(canonical_product=product, is_active=True),
        'reports_page': reports_page,
        'currency_stats': currency_stats,
        'total_reports': analysis_reports.count(),
        'current_report_count': len(current_report_ids),
        'business_count': comparison_store_count,
        'comparison_store_count': comparison_store_count,
        'location_count': current_reports.filter(latitude__isnull=False, longitude__isnull=False).count(),
        'latest_report': base_reports.first(),
        'comparison_currency': comparison_currency,
        'comparison_reports': comparison_reports,
        'comparison_has_multiple_stores': len(comparison_reports) > 1,
        'comparison_savings_amount': comparison_savings_amount,
        'comparison_savings_percent': comparison_savings_percent,
        'cheapest_report': cheapest_report,
        'most_expensive_report': most_expensive_report,
        'nearby_cheapest_report': nearby_cheapest_report,
        'nearby_most_expensive_report': nearby_most_expensive_report,
        'nearest_reports': nearest_reports,
        'reports_with_location': reports_with_location,
        'current_sort': sort,
        'search_query': query,
        'user_lat': user_lat,
        'user_lng': user_lng,
        'is_watching': is_watching,
        'catalog_images': product.catalog_images.all(),
        'product_photos': product_photos,
    }
    return render(request, 'product_detail.html', context)


def product_list(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'popular')

    products = Product.objects.prefetch_related('tags', 'catalog_images').annotate(
        report_count=Count('price_reports', distinct=True),
        business_count=Count('price_reports__business', distinct=True),
        min_price=Min('price_reports__price'),
        max_price=Max('price_reports__price'),
        avg_price=Avg('price_reports__price'),
        latest_observed=Max('price_reports__observed_at'),
    )

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(aliases__alias_name__icontains=query)
            | Q(tags__name__icontains=query)
        ).distinct()

    if sort == 'name':
        products = products.order_by('name')
    elif sort == 'cheapest':
        products = products.order_by('min_price', 'name')
    elif sort == 'expensive':
        products = products.order_by('-max_price', 'name')
    elif sort == 'recent':
        products = products.order_by('-latest_observed', 'name')
    else:
        products = products.order_by('-report_count', 'name')

    paginator = Paginator(products, 30)
    page_number = request.GET.get('page', 1)
    try:
        products_page = paginator.page(page_number)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    latest_reports = PriceReport.objects.filter(
        product_id__in=[product.id for product in products_page.object_list],
        marked_for_deletion=False,
    ).select_related('business', 'business_branch').order_by('product_id', '-observed_at')
    latest_by_product = {}
    for report in latest_reports:
        latest_by_product.setdefault(report.product_id, report)

    for product in products_page.object_list:
        product.latest_report = latest_by_product.get(product.id)

    return render(request, 'product_list.html', {
        'products_page': products_page,
        'search_query': query,
        'current_sort': sort,
    })


def product_price_analysis(request, pk):
    product = get_object_or_404(Product.objects.prefetch_related('tags', 'aliases'), pk=pk)
    product_ids = _product_family_ids(product)
    reports = PriceReport.objects.filter(
        product_id__in=product_ids,
        marked_for_deletion=False,
    ).select_related('business', 'business_branch').order_by('observed_at')

    currency = request.GET.get('currency') or reports.values_list('currency', flat=True).first() or 'PGK'
    currency_reports = reports.filter(currency=currency)
    stats = currency_reports.aggregate(
        count=Count('id'), min_price=Min('price'), max_price=Max('price'), avg_price=Avg('price')
    )
    timeline = list(currency_reports.values('observed_at', 'price', 'business__name')[:250])
    heatmap_reports = currency_reports.filter(latitude__isnull=False, longitude__isnull=False)[:250]
    by_business = currency_reports.values('business__name').annotate(
        count=Count('id'), avg_price=Avg('price'), min_price=Min('price'), max_price=Max('price')
    ).order_by('-count', 'business__name')[:25]
    currencies = reports.values('currency').annotate(count=Count('id')).order_by('currency')
    return render(request, 'product_price_analysis.html', {
        'product': product, 'reports': currency_reports, 'stats': stats, 'timeline': timeline,
        'heatmap_reports': heatmap_reports, 'by_business': by_business, 'currencies': currencies, 'currency': currency,
    })
