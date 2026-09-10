from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import PriceReport
from .share_services import build_price_share_context


def _get_report(pk):
    return get_object_or_404(
        PriceReport.objects.select_related(
            'product',
            'business',
            'business_branch',
            'user',
            'user__profile',
        ).prefetch_related('photos'),
        pk=pk,
    )


def price_share_page(request, pk):
    report = _get_report(pk)
    base_url = request.build_absolute_uri('/').rstrip('/')
    share = build_price_share_context(report, base_url=base_url)
    return render(request, 'price_share.html', {
        'report': report,
        'share': share,
    })


def price_share_data(request, pk):
    report = _get_report(pk)
    base_url = request.build_absolute_uri('/').rstrip('/')
    return JsonResponse(build_price_share_context(report, base_url=base_url))
