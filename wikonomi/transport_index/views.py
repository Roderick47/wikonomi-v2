"""Webhook and public views for the transport index app."""

import importlib
import importlib.util
import json
import logging

from django.core import signing
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import ProfileCompletionForm
from .models import CabDriver, CabStatus, ContactAttempt
from .router import dispatch_inbound_message
from .services import FRESHNESS_MINUTES
from .whatsapp_client import get_webhook_verify_token

logger = logging.getLogger(__name__)

if importlib.util.find_spec('ratelimit'):
    ratelimit = importlib.import_module('ratelimit.decorators').ratelimit
else:
    def ratelimit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


def _parse_inbound_messages(payload):
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            metadata = value.get('metadata', {})
            contacts = {contact.get('wa_id'): contact for contact in value.get('contacts', [])}
            for message in value.get('messages', []):
                sender = message.get('from')
                yield {
                    'id': message.get('id'),
                    'from': sender,
                    'timestamp': message.get('timestamp'),
                    'type': message.get('type'),
                    'text': message.get('text', {}).get('body'),
                    'interactive': message.get('interactive'),
                    'raw': message,
                    'contact': contacts.get(sender),
                    'metadata': metadata,
                }


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def whatsapp_webhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        verify_token = get_webhook_verify_token()
        if verify_token and mode == 'subscribe' and token == verify_token and challenge is not None:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponseForbidden('Webhook verification failed')

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    dispatched = 0
    for inbound_message in _parse_inbound_messages(payload):
        dispatch_inbound_message(inbound_message, metadata=inbound_message.get('metadata'))
        dispatched += 1

    if dispatched == 0:
        logger.debug('WhatsApp webhook payload contained no inbound messages', extra={'payload': payload})

    return JsonResponse({'status': 'ok', 'dispatched': dispatched})


def cab_list(request):
    drivers = CabDriver.objects.select_related('status').filter(is_verified=True, is_active_listing=True)
    vehicle_type = request.GET.get('vehicle_type')
    area = request.GET.get('area')
    available_now = request.GET.get('available') == '1'

    if vehicle_type:
        drivers = drivers.filter(vehicle_type=vehicle_type)
    if area:
        drivers = drivers.filter(home_area__icontains=area)
    if available_now:
        cutoff = timezone.now() - timezone.timedelta(minutes=FRESHNESS_MINUTES)
        drivers = drivers.filter(
            status__availability=CabStatus.Availability.AVAILABLE,
            status__last_updated__gte=cutoff,
        )

    return render(
        request,
        'transport_index/cab_list.html',
        {'drivers': drivers.order_by('home_area', 'display_name'), 'vehicle_types': CabDriver.VehicleType.choices},
    )


def cab_profile(request, slug):
    driver = get_object_or_404(CabDriver.objects.select_related('status'), slug=slug)
    return render(request, 'transport_index/cab_profile.html', {'driver': driver})


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@ratelimit(key='ip', rate='20/h', block=True)
def cab_contact(request, slug):
    driver = get_object_or_404(CabDriver, slug=slug)
    ContactAttempt.objects.create(
        driver=driver,
        ip_address=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return redirect(driver.whatsapp_deep_link())


def setup_profile(request, token):
    try:
        data = signing.loads(token, salt='transport-index-setup', max_age=60 * 60 * 24 * 7)
    except signing.BadSignature:
        return render(request, 'transport_index/setup_invalid.html', status=403)

    driver = get_object_or_404(CabDriver, id=data.get('driver_id'))
    if request.method == 'POST':
        form = ProfileCompletionForm(request.POST, request.FILES, instance=driver)
        if form.is_valid():
            driver = form.save(commit=False)
            driver.profile_completeness = CabDriver.ProfileCompleteness.COMPLETE
            driver.save()
            return redirect('transport_index:cab_profile', slug=driver.slug)
    else:
        form = ProfileCompletionForm(instance=driver)

    return render(request, 'transport_index/setup_profile.html', {'form': form, 'driver': driver})


def robots_txt(request):
    return HttpResponse(
        'User-agent: *\nDisallow: /cabs/*/contact/\nAllow: /cabs/\n',
        content_type='text/plain',
    )
