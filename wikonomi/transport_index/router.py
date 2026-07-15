import logging
import time

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.urls import reverse

from .gazetteer import match_place
from .llm_fallback import extract_intent
from .models import CabDriver, CabStatus, RouterEvent
from .services import nearest_available_drivers
from .whatsapp_client import send_interactive_list, send_text

logger = logging.getLogger(__name__)
SESSION_TTL_SECONDS = 3600
SERVICE_WINDOW_SECONDS = 24 * 3600


def _key(phone, suffix):
    return f'transport_index:session:{phone}:{suffix}'


def _reply(to, body):
    try:
        return send_text(to, body)
    except Exception:
        logger.exception('WhatsApp send failed')
        return None


def _event(phone, stage, message_type='', detail=None):
    RouterEvent.objects.create(
        phone_number=phone or '',
        stage=stage,
        message_type=message_type or '',
        detail=detail or {},
    )


def _location(message):
    location = (message.get('raw') or {}).get('location') or {}
    if location.get('latitude') is not None and location.get('longitude') is not None:
        return location
    return None


def _setup_url(driver):
    token = signing.dumps({'driver_id': driver.id}, salt='transport-index-setup')
    base_url = getattr(settings, 'WIKONOMI_BASE_URL', 'https://wikonomi.com')
    return f"{base_url}{reverse('transport_index:setup_profile', args=[token])}"


def _send_results(phone, latitude, longitude):
    results = nearest_available_drivers(latitude, longitude)
    if not results:
        _reply(phone, 'No verified available cabs were found nearby right now. Please try again soon.')
        return

    rows = []
    for item in results:
        driver = item['driver']
        status = item['status']
        rows.append({
            'id': f'cab-{driver.id}',
            'title': driver.display_name[:24],
            'description': (
                f"{driver.get_vehicle_type_display()} • "
                f"{item['distance_km']:.1f} km • seen {status.last_seen_minutes()} min ago"
            ),
        })

    try:
        send_interactive_list(phone, 'Nearby Wikonomi cabs', rows)
    except Exception:
        logger.exception('WhatsApp list send failed')
        _reply(phone, '\n'.join([f"{row['title']} — {row['description']}" for row in rows]))


def _handle_wizard(phone, text, state):
    text = (text or '').strip()
    if state == 'awaiting_name':
        cache.set(_key(phone, 'temp_name'), text[:120], SESSION_TTL_SECONDS)
        cache.set(_key(phone, 'state'), 'awaiting_vehicle_type', SESSION_TTL_SECONDS)
        _reply(phone, 'Choose vehicle type:\n1. Taxi\n2. PMV\n3. Informal')
        return True

    if state == 'awaiting_vehicle_type':
        mapping = {
            '1': 'taxi',
            'taxi': 'taxi',
            '2': 'pmv',
            'pmv': 'pmv',
            '3': 'informal',
            'informal': 'informal',
        }
        choice = mapping.get(text.lower())
        if not choice:
            _reply(phone, 'Please reply 1 for Taxi, 2 for PMV, or 3 for Informal.')
            return True
        cache.set(_key(phone, 'temp_vehicle_type'), choice, SESSION_TTL_SECONDS)
        cache.set(_key(phone, 'state'), 'awaiting_plate', SESSION_TTL_SECONDS)
        _reply(phone, 'What is your vehicle plate number?')
        return True

    if state == 'awaiting_plate':
        driver = CabDriver.objects.create(
            whatsapp_number=phone,
            display_name=cache.get(_key(phone, 'temp_name')) or 'Wikonomi Driver',
            vehicle_type=cache.get(_key(phone, 'temp_vehicle_type')) or CabDriver.VehicleType.TAXI,
            vehicle_plate=text[:40],
            profile_completeness=CabDriver.ProfileCompleteness.MINIMAL,
        )
        CabStatus.objects.create(driver=driver, availability=CabStatus.Availability.OFFLINE)
        for suffix in ('temp_name', 'temp_vehicle_type'):
            cache.delete(_key(phone, suffix))
        cache.set(_key(phone, 'state'), 'idle', SESSION_TTL_SECONDS)
        _reply(phone, f'Thanks {driver.display_name}! Your cab profile is created. Share your live location when available.')
        _reply(phone, f'Want more riders to pick you? Add a photo: {_setup_url(driver)}')
        return True

    return False


def dispatch_inbound_message(message, metadata=None):
    phone = message.get('from')
    message_type = message.get('type')
    text = (message.get('text') or '').strip()
    lowered = text.lower()
    cache.set(_key(phone, 'last_inbound_at'), int(time.time()), SERVICE_WINDOW_SECONDS)

    location = _location(message)
    driver = CabDriver.objects.filter(whatsapp_number=phone).first()

    if location and driver:
        status, _ = CabStatus.objects.get_or_create(driver=driver)
        status.latitude = location['latitude']
        status.longitude = location['longitude']
        status.area_label = location.get('name', '')
        status.availability = (
            status.availability
            if status.availability == CabStatus.Availability.BUSY
            else CabStatus.Availability.AVAILABLE
        )
        status.save()
        _event(phone, RouterEvent.Stage.LOCATION_UPDATE, message_type)
        _reply(phone, 'Location updated ✅')
        return 'location_update'

    if lowered in {'busy', 'offline', 'available', 'pause', 'stop'} and driver:
        status, _ = CabStatus.objects.get_or_create(driver=driver)
        if lowered in {'pause', 'stop'}:
            driver.is_active_listing = False
            driver.save(update_fields=['is_active_listing'])
            _reply(phone, 'Your listing is paused. Reply AVAILABLE to appear again.')
        elif lowered == 'available':
            driver.is_active_listing = True
            driver.save(update_fields=['is_active_listing'])
            status.availability = CabStatus.Availability.AVAILABLE
            status.save(update_fields=['availability', 'last_updated'])
            _reply(phone, 'You are marked available ✅')
        else:
            status.availability = lowered
            status.save(update_fields=['availability', 'last_updated'])
            _reply(phone, f'You are marked {lowered}.')
        _event(phone, RouterEvent.Stage.KEYWORD_MATCH, message_type, {'keyword': lowered})
        return 'keyword_match'

    state = cache.get(_key(phone, 'state'), 'idle')
    if state != 'idle':
        handled = _handle_wizard(phone, text, state)
        _event(phone, RouterEvent.Stage.WIZARD_STEP, message_type, {'state': state})
        return 'wizard_step' if handled else None

    if location:
        _event(phone, RouterEvent.Stage.RIDER_LOCATION, message_type)
        _send_results(phone, location['latitude'], location['longitude'])
        return 'rider_location'

    if not driver and lowered == 'driver':
        cache.set(_key(phone, 'state'), 'awaiting_name', SESSION_TTL_SECONDS)
        _event(phone, RouterEvent.Stage.WIZARD_STEP, message_type, {'state': 'awaiting_name'})
        _reply(phone, 'What is your display name?')
        return 'wizard_start'

    if lowered in {'find cab', 'taxi', 'need a ride', 'cab', 'find taxi'}:
        _event(phone, RouterEvent.Stage.KEYWORD_MATCH, message_type, {'keyword': lowered})
        _reply(phone, 'Please share your WhatsApp location so we can find nearby cabs.')
        return 'rider_prompt_location'

    place = match_place(text)
    if place:
        _event(phone, RouterEvent.Stage.GAZETTEER_HIT, message_type, place)
        _send_results(phone, place['latitude'], place['longitude'])
        return 'gazetteer_hit'

    extracted = extract_intent(text) if text else {'intent': 'unknown'}
    _event(phone, RouterEvent.Stage.LLM_FALLBACK, message_type, extracted)
    if extracted.get('intent') in {'find_cab', 'ride'}:
        _reply(phone, 'Please share your WhatsApp location so we can find nearby cabs.')
    else:
        _reply(phone, 'Reply DRIVER to list your taxi/PMV, or share your location to find nearby cabs.')
    return 'llm_fallback'
