import difflib
import importlib
import importlib.util
import logging
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)
GAZETTEER = {
    'boroko': (-9.4680, 147.1950),
    'waigani': (-9.4438, 147.1836),
    'gordons': (-9.4372, 147.1960),
    'gerehu': (-9.3980, 147.1640),
    'hohola': (-9.4590, 147.1750),
    'konedobu': (-9.4740, 147.1510),
    'foodworld waigani': (-9.4431, 147.1830),
    'vision city': (-9.4416, 147.1829),
    'ela beach': (-9.4810, 147.1530),
    'downtown port moresby': (-9.4789, 147.1508),
    'airport': (-9.4434, 147.2209),
    'jacksons airport': (-9.4434, 147.2209),
    'university of png': (-9.4077, 147.1705),
    'nine mile': (-9.4120, 147.2400),
    'six mile': (-9.4440, 147.2350),
}


def _rapidfuzz_modules():
    if importlib.util.find_spec('rapidfuzz'):
        return (
            importlib.import_module('rapidfuzz.process'),
            importlib.import_module('rapidfuzz.fuzz'),
        )
    if not settings.DEBUG and 'test' not in sys.argv:
        raise ImproperlyConfigured('rapidfuzz must be installed for production gazetteer matching.')
    return None, None


def _best_match(text):
    rapid_process, rapid_fuzz = _rapidfuzz_modules()
    if rapid_process and rapid_fuzz:
        match = rapid_process.extractOne(text, GAZETTEER.keys(), scorer=rapid_fuzz.WRatio)
        if match:
            return match[0], match[1]

    matches = difflib.get_close_matches(text, GAZETTEER.keys(), n=1, cutoff=0)
    if not matches:
        return None, 0
    name = matches[0]
    return name, int(difflib.SequenceMatcher(None, text, name).ratio() * 100)


def match_place(text, threshold=86):
    if not text:
        return None
    name, score = _best_match(text.lower())
    if not name:
        return None
    logger.info('Transport gazetteer match', extra={'query': text, 'match': name, 'score': score})
    if score >= threshold:
        lat, lng = GAZETTEER[name]
        return {'name': name.title(), 'latitude': lat, 'longitude': lng, 'score': score}
    return None
