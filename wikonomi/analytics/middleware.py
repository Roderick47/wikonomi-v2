import hashlib
import logging
import threading
import time

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from .models import SiteVisit

logger = logging.getLogger(__name__)


class SiteVisitTrackingMiddleware:
    """Record sampled human page visits when in-app analytics is enabled."""

    IGNORED_PREFIXES = (
        '/admin/',
        '/analytics/',
        '/static/',
        '/media/',
        '/favicon',
        '/robots.txt',
        '/sitemap.xml',
    )

    # Keep this intentionally broad. SiteVisit is optional analytics, so it is
    # better to miss a non-browser automation request than to let crawlers write
    # thousands of rows into the production database.
    BOT_UA_MARKERS = (
        'bot',
        'crawler',
        'spider',
        'slurp',
        'headless',
        'facebookexternalhit',
        'preview',
        'wget/',
        'curl/',
        'python-requests',
        'python-httpx',
        'aiohttp',
        'scrapy',
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self._recent_visitors = {}
        self._rate_limit_lock = threading.Lock()

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self.track_visit(request, response)
        except DatabaseError:
            # Analytics must fail open: losing one visit is preferable to turning
            # an otherwise successful page response into a site-wide 500.
            logger.exception('Unable to record site visit analytics')
        return response

    def is_known_bot(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '').strip().lower()
        if not user_agent:
            return True
        return any(marker in user_agent for marker in self.BOT_UA_MARKERS)

    def should_track(self, request, response):
        if not getattr(settings, 'SITE_VISIT_ANALYTICS_ENABLED', True):
            return False
        if request.method != 'GET':
            return False
        if response.status_code >= 400:
            return False
        if any(request.path.startswith(prefix) for prefix in self.IGNORED_PREFIXES):
            return False
        if self.is_known_bot(request):
            return False
        content_type = response.get('Content-Type', '')
        return 'text/html' in content_type

    def get_page_type(self, request):
        url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
        if url_name == 'about':
            return SiteVisit.PageType.ABOUT
        if url_name == 'price_detail':
            return SiteVisit.PageType.PRICE_DETAIL
        return SiteVisit.PageType.PAGE

    def get_visitor_key(self, request):
        if request.user.is_authenticated:
            return f'user:{request.user.pk}'
        if request.session.session_key:
            return f'session:{request.session.session_key}'

        raw_key = '|'.join([
            request.META.get('REMOTE_ADDR', ''),
            request.META.get('HTTP_USER_AGENT', ''),
            settings.SECRET_KEY,
        ])
        return f'anon:{hashlib.sha256(raw_key.encode()).hexdigest()[:32]}'

    def is_rate_limited(self, visitor_key):
        interval = max(
            0,
            int(getattr(settings, 'SITE_VISIT_MIN_INTERVAL_SECONDS', 60)),
        )
        if interval == 0:
            return False

        now = time.monotonic()
        with self._rate_limit_lock:
            last_seen = self._recent_visitors.get(visitor_key)
            if last_seen is not None and now - last_seen < interval:
                return True

            self._recent_visitors[visitor_key] = now

            # Bound process memory if analytics is temporarily enabled during a
            # high-traffic period. This is deliberately process-local so the
            # throttle itself never touches PostgreSQL.
            if len(self._recent_visitors) > 10000:
                cutoff = now - interval
                self._recent_visitors = {
                    key: seen_at
                    for key, seen_at in self._recent_visitors.items()
                    if seen_at >= cutoff
                }

        return False

    def track_visit(self, request, response):
        if not self.should_track(request, response):
            return

        visitor_key = self.get_visitor_key(request)
        if self.is_rate_limited(visitor_key):
            return

        user = request.user if request.user.is_authenticated else None
        SiteVisit.objects.create(
            user=user,
            visitor_key=visitor_key,
            path=request.path[:500],
            page_type=self.get_page_type(request),
            referrer=request.META.get('HTTP_REFERER', '')[:500],
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            ip_address=request.META.get('REMOTE_ADDR'),
            timestamp=timezone.now(),
        )
