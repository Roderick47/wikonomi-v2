import json
import logging
import os
from decimal import Decimal

import requests

from .models import LLMFallbackLog

logger = logging.getLogger(__name__)
MODEL = 'claude-haiku-4-5-20251001'
SYSTEM_PROMPT = (
    'You extract transport intent and Port Moresby/PNG place names for Wikonomi. '
    'Return compact JSON with intent and place. '
    * 80
)


def _cost_per_million_tokens(env_name):
    return Decimal(os.environ.get(env_name, '0'))


def estimate_cost_usd(input_tokens, output_tokens):
    input_cost = Decimal(input_tokens) * _cost_per_million_tokens('ANTHROPIC_HAIKU_INPUT_COST_PER_MILLION')
    output_cost = Decimal(output_tokens) * _cost_per_million_tokens('ANTHROPIC_HAIKU_OUTPUT_COST_PER_MILLION')
    return (input_cost + output_cost) / Decimal('1000000')


def extract_intent(text):
    token = os.environ.get('ANTHROPIC_API_KEY')
    if not token:
        LLMFallbackLog.objects.create(
            input_text=text,
            extracted_intent='unavailable',
            raw_response={'error': 'ANTHROPIC_API_KEY not configured'},
        )
        return {'intent': 'unknown', 'place': ''}

    payload = {
        'model': MODEL,
        'max_tokens': 80,
        'system': [{'type': 'text', 'text': SYSTEM_PROMPT, 'cache_control': {'type': 'ephemeral'}}],
        'messages': [{'role': 'user', 'content': f'Extract intent/place as JSON only: {text}'}],
    }
    response = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': token,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    content = ''.join(part.get('text', '') for part in data.get('content', []) if part.get('type') == 'text')
    try:
        extracted = json.loads(content)
    except json.JSONDecodeError:
        extracted = {'intent': 'unknown', 'place': '', 'raw': content}
    usage = data.get('usage', {})
    input_tokens = usage.get('input_tokens', 0)
    output_tokens = usage.get('output_tokens', 0)
    LLMFallbackLog.objects.create(
        input_text=text,
        extracted_intent=extracted.get('intent', ''),
        raw_response=data,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost_usd(input_tokens, output_tokens),
    )
    return extracted
