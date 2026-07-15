"""Webhook views for WhatsApp Business Cloud API callbacks."""

import json
import logging

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .router import dispatch_inbound_message
from .whatsapp_client import get_webhook_verify_token

logger = logging.getLogger(__name__)


def _parse_inbound_messages(payload):
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            metadata = value.get('metadata', {})
            contacts = {
                contact.get('wa_id'): contact
                for contact in value.get('contacts', [])
            }
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
    """Verify and receive WhatsApp Cloud API webhook requests."""
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        verify_token = get_webhook_verify_token()
        if (
            verify_token
            and mode == 'subscribe'
            and token == verify_token
            and challenge is not None
        ):
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
        logger.debug(
            'WhatsApp webhook payload contained no inbound messages',
            extra={'payload': payload},
        )

    return JsonResponse({'status': 'ok', 'dispatched': dispatched})
