from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from catalog.value import (
    VALUE_STALE_AFTER_DAYS,
    build_basket_comparison,
    build_product_value_comparison,
)

from .models import Product, ShoppingList


def _currency_from_request(request):
    value = (request.GET.get('currency') or 'PGK').strip().upper()
    return value[:3] if len(value) >= 3 else 'PGK'


def product_value_analysis(request, pk):
    product = get_object_or_404(
        Product.objects.select_related('category', 'identity').prefetch_related('tags', 'aliases'),
        pk=pk,
    )
    currency = _currency_from_request(request)
    comparison = build_product_value_comparison(
        product,
        currency=currency,
        stale_after_days=VALUE_STALE_AFTER_DAYS,
    )
    return render(request, 'product_value_analysis.html', {
        'product': product,
        'currency': currency,
        'comparison': comparison,
    })


@login_required
def shopping_list_compare(request):
    lists = request.user.shopping_lists.all()
    if not lists.exists():
        ShoppingList.objects.create(user=request.user, name='My Shopping List')
        lists = request.user.shopping_lists.all()

    active_list = lists.first()
    items = list(
        active_list.items.select_related(
            'product',
            'product__category',
            'product__identity',
        ).order_by('is_checked', '-created_at')
    ) if active_list else []

    currency = _currency_from_request(request)
    comparison = build_basket_comparison(
        items,
        currency=currency,
        stale_after_days=VALUE_STALE_AFTER_DAYS,
    )
    return render(request, 'shopping_list_compare.html', {
        'shopping_lists': lists,
        'active_list': active_list,
        'items': items,
        'currency': currency,
        'comparison': comparison,
    })
