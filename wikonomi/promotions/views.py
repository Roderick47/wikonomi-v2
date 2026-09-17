from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import Business, BusinessNormalizationService

from .forms import PromotionForm
from .models import Promotion, PromotionConfirmation


def _promotions_available(request):
    return getattr(settings, 'PROMOTIONS_ENABLED', False) or (
        request.user.is_authenticated and request.user.is_staff
    )


def _require_promotions(request):
    if not _promotions_available(request):
        raise Http404


def contribute(request):
    """Intent-first posting gateway: users choose what they actually observed."""
    return render(request, 'promotions/contribute.html', {
        'promotions_available': _promotions_available(request),
    })


def promotion_list(request):
    _require_promotions(request)
    query = request.GET.get('q', '').strip()

    active_promotions = Promotion.objects.active().select_related(
        'business', 'business_branch', 'created_by'
    ).prefetch_related(
        'targets__product', 'targets__category', 'targets__subcategory'
    )

    if query:
        active_promotions = active_promotions.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(business__name__icontains=query)
            | Q(targets__product__name__icontains=query)
            | Q(targets__category__name__icontains=query)
            | Q(targets__subcategory__name__icontains=query)
        ).distinct()

    upcoming_promotions = Promotion.objects.upcoming().select_related(
        'business', 'business_branch'
    ).prefetch_related(
        'targets__product', 'targets__category', 'targets__subcategory'
    )[:8]

    return render(request, 'promotions/list.html', {
        'active_promotions': active_promotions,
        'upcoming_promotions': upcoming_promotions,
        'search_query': query,
    })


def promotion_detail(request, pk):
    _require_promotions(request)
    promotion = get_object_or_404(
        Promotion.objects.select_related(
            'business', 'business_branch', 'created_by'
        ).prefetch_related(
            'targets__product', 'targets__category', 'targets__subcategory',
            'confirmations__user',
        ),
        pk=pk,
    )
    return render(request, 'promotions/detail.html', {
        'promotion': promotion,
        'active_confirmation_count': promotion.confirmations.filter(is_still_active=True).count(),
        'ended_confirmation_count': promotion.confirmations.filter(is_still_active=False).count(),
    })


def _promotion_form_context(request, form):
    return {
        'form': form,
        'businesses': Business.objects.order_by('name'),
        'cancel_url': request.GET.get('next') or reverse('promotions:list'),
    }


def promotion_create(request):
    _require_promotions(request)

    initial = {}
    for key in ('business', 'product', 'category', 'subcategory', 'scope'):
        value = request.GET.get(key)
        if value:
            initial[key] = value

    if request.GET.get('business_name'):
        initial['business_name'] = request.GET['business_name'].strip()
    elif initial.get('business'):
        try:
            initial['business_name'] = Business.objects.get(pk=initial['business']).name
        except (Business.DoesNotExist, TypeError, ValueError):
            pass

    if request.method == 'POST':
        form = PromotionForm(request.POST, request.FILES)
        if form.is_valid():
            business_name = form.cleaned_data['business_name']
            business, _normalized_branch, _was_created = (
                BusinessNormalizationService.normalize_price_report_data(
                    business_name=business_name,
                    location='',
                )
            )

            selected_branch = form.cleaned_data.get('business_branch')
            if selected_branch and selected_branch.canonical_business_id != business.id:
                form.add_error('business_branch', 'Choose a branch belonging to this store.')
            else:
                promotion = form.save(commit=False)
                promotion.business = business
                promotion.business_branch = selected_branch
                if request.user.is_authenticated:
                    promotion.created_by = request.user
                if request.user.is_authenticated and request.user.is_staff:
                    promotion.source = Promotion.Source.ADMIN
                    promotion.is_verified = True
                promotion.full_clean()
                promotion.save()
                form.save_target(promotion)
                messages.success(
                    request,
                    'Special reported. Wikonomi will stop showing it as active when it expires.',
                )
                return redirect(promotion.get_absolute_url())
    else:
        form = PromotionForm(initial=initial)

    return render(request, 'promotions/form.html', _promotion_form_context(request, form))


@login_required
@require_POST
def confirm_promotion(request, pk):
    _require_promotions(request)
    promotion = get_object_or_404(Promotion, pk=pk)
    value = request.POST.get('active')
    if value not in {'yes', 'no'}:
        return JsonResponse({'error': 'Invalid confirmation value.'}, status=400)

    confirmation, _ = PromotionConfirmation.objects.update_or_create(
        promotion=promotion,
        user=request.user,
        defaults={'is_still_active': value == 'yes'},
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'is_still_active': confirmation.is_still_active,
            'active_count': promotion.confirmations.filter(is_still_active=True).count(),
            'ended_count': promotion.confirmations.filter(is_still_active=False).count(),
        })

    messages.success(
        request,
        'Thanks — your confirmation helps keep specials current.'
        if confirmation.is_still_active
        else 'Thanks — you marked this special as no longer running.',
    )
    return redirect(promotion.get_absolute_url())
