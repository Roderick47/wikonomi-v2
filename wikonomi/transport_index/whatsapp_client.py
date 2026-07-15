"""Client helpers for the WhatsApp Business Cloud API.

The functions in this module are intentionally small and importable so other
apps can reuse them when they need to send WhatsApp messages through the same
Meta Cloud API configuration.
"""

import os

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DEFAULT_API_VERSION = 'v22.0'
GRAPH_API_BASE_URL = 'https://graph.facebook.com'


def get_whatsapp_setting(name, default=None):
    """Read a WhatsApp setting from Django settings or the environment."""
    return getattr(settings, name, None) or os.environ.get(name, default)


def get_webhook_verify_token():
    """Return the configured webhook verification token."""
    return get_whatsapp_setting('WHATSAPP_WEBHOOK_VERIFY_TOKEN')


def _get_api_version():
    return get_whatsapp_setting('WHATSAPP_API_VERSION', DEFAULT_API_VERSION)


def _get_token():
    token = get_whatsapp_setting('WHATSAPP_TOKEN')
    if not token:
        raise ImproperlyConfigured('WHATSAPP_TOKEN is required to send WhatsApp messages.')
    return token


def _get_phone_number_id():
    phone_number_id = get_whatsapp_setting('WHATSAPP_PHONE_NUMBER_ID')
    if not phone_number_id:
        raise ImproperlyConfigured('WHATSAPP_PHONE_NUMBER_ID is required to send WhatsApp messages.')
    return phone_number_id


def _messages_url():
    return f'{GRAPH_API_BASE_URL}/{_get_api_version()}/{_get_phone_number_id()}/messages'


def _log_message(payload, status, response=None, error=''):
    from .models import WhatsAppMessageLog

    WhatsAppMessageLog.objects.create(
        recipient=payload.get('to', ''),
        message_type=payload.get('type', ''),
        status=status,
        payload=payload,
        response=response or {},
        error=error,
    )


def _post_message(payload):
    from .models import WhatsAppMessageLog

    try:
        response = requests.post(
            _messages_url(),
            headers={
                'Authorization': f'Bearer {_get_token()}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        response_body = {}
        if getattr(exc, 'response', None) is not None:
            try:
                response_body = exc.response.json()
            except ValueError:
                response_body = {'body': exc.response.text}
        _log_message(payload, WhatsAppMessageLog.Status.FAILED, response=response_body, error=str(exc))
        raise

    response_json = response.json()
    _log_message(payload, WhatsAppMessageLog.Status.SENT, response=response_json)
    return response_json


def send_text(to, body):
    """Send a plain text WhatsApp message."""
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'text',
        'text': {'preview_url': False, 'body': body},
    }
    return _post_message(payload)


def _normalise_list_row(row):
    if isinstance(row, str):
        return {'id': row, 'title': row[:24]}

    normalised = {
        'id': str(row['id']),
        'title': str(row['title'])[:24],
    }
    description = row.get('description')
    if description:
        normalised['description'] = str(description)[:72]
    return normalised


def send_interactive_list(to, header, rows):
    """Send an interactive list message.

    ``rows`` may be a flat iterable of row dictionaries/strings or an iterable
    of section dictionaries with ``title`` and ``rows`` keys.
    """
    sections = []
    rows = list(rows)
    if rows and isinstance(rows[0], dict) and 'rows' in rows[0]:
        for section in rows:
            sections.append({
                'title': str(section.get('title', 'Options'))[:24],
                'rows': [_normalise_list_row(row) for row in section.get('rows', [])],
            })
    else:
        sections.append({
            'title': 'Options',
            'rows': [_normalise_list_row(row) for row in rows],
        })

    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'list',
            'header': {'type': 'text', 'text': str(header)[:60]},
            'body': {'text': str(header)[:1024]},
            'action': {
                'button': 'Choose',
                'sections': sections,
            },
        },
    }
    return _post_message(payload)
