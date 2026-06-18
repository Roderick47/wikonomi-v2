from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Avg, Count, Max, Min, Q
from django.shortcuts import get_object_or_404, render

from .models import Product, ProductAlias, PriceLike, PriceReport, ProductWatchlist
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


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.prefetch_related('tags', 'aliases'), pk=pk)
    product_ids = _product_family_ids(product)

    base_reports = PriceReport.objects.filter(product_id__in=product_ids).select_related(
        'product',
        'business',
        'business_branch',
        'user',
        'user__profile',
    ).prefetch_related('product__tags', 'likes').annotate(
        average_rating=Avg('ratings__rating'),
        rating_count=Count('ratings'),
    ).order_by('-observed_at')

    user_lat, user_lng = _parse_location(request)
    sort = request.GET.get('sort', 'recent')
    reports = base_reports

    nearby_reports = PriceReport.objects.none()
    if user_lat is not None and user_lng is not None:
        nearby_reports = annotate_with_distance(
            base_reports.filter(latitude__isnull=False, longitude__isnull=False),
            user_lat,
            user_lng,
            radius_hexes=4,
        )
        if sort == 'nearest':
            reports = nearby_reports

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
        reports_page = paginator.page(paginator.num_pages)

    reports_page.object_list = _with_user_card_state(request, reports_page.object_list)

    currency_stats = list(base_reports.values('currency').annotate(
        report_count=Count('id'),
        min_price=Min('price'),
        max_price=Max('price'),
        avg_price=Avg('price'),
        latest_observed=Max('observed_at'),
    ).order_by('-report_count', 'currency'))

    cheapest_report = base_reports.order_by('price', '-observed_at').first()
    most_expensive_report = base_reports.order_by('-price', '-observed_at').first()
    nearest_reports = []
    nearby_cheapest_report = None
    nearby_most_expensive_report = None

    if user_lat is not None and user_lng is not None:
        nearest_reports = _with_user_card_state(request, nearby_reports[:5])
        nearby_cheapest_report = nearby_reports.order_by('price', 'distance_km').first()
        nearby_most_expensive_report = nearby_reports.order_by('-price', 'distance_km').first()

    if nearby_cheapest_report is None:
        nearby_cheapest_report = cheapest_report
    if nearby_most_expensive_report is None:
        nearby_most_expensive_report = most_expensive_report

    reports_with_location = base_reports.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    )[:100]

    is_watching = False
    if request.user.is_authenticated:
        is_watching = ProductWatchlist.objects.filter(user=request.user, product=product).exists()

    context = {
        'product': product,
        'aliases': ProductAlias.objects.filter(canonical_product=product, is_active=True),
        'reports_page': reports_page,
        'currency_stats': currency_stats,
        'total_reports': base_reports.count(),
        'business_count': base_reports.exclude(business__isnull=True).values('business_id').distinct().count(),
        'location_count': base_reports.filter(latitude__isnull=False, longitude__isnull=False).count(),
        'latest_report': base_reports.first(),
        'cheapest_report': cheapest_report,
        'most_expensive_report': most_expensive_report,
        'nearby_cheapest_report': nearby_cheapest_report,
        'nearby_most_expensive_report': nearby_most_expensive_report,
        'nearest_reports': nearest_reports,
        'reports_with_location': reports_with_location,
        'current_sort': sort,
        'user_lat': user_lat,
        'user_lng': user_lng,
        'is_watching': is_watching,
    }
    return render(request, 'product_detail.html', context)


def product_list(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'popular')

    products = Product.objects.prefetch_related('tags').annotate(
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
        product_id__in=[product.id for product in products_page.object_list]
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
