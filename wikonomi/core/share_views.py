from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import PriceReport
from .share_services import build_price_share_context


def price_share_data(request, pk):
    report = get_object_or_404(
        PriceReport.objects.select_related('product', 'business', 'business_branch'),
        pk=pk,
    )
    base_url = request.build_absolute_uri('/').rstrip('/')
    return JsonResponse(build_price_share_context(report, base_url=base_url))
