import hashlib

from django.conf import settings
from django.utils import timezone

from .models import SiteVisit


class SiteVisitTrackingMiddleware:
    """Record lightweight page visit analytics for dashboard traffic metrics."""

    IGNORED_PREFIXES = (
        '/admin/',
        '/analytics/',
        '/static/',
        '/media/',
        '/favicon',
        '/robots.txt',
        '/sitemap.xml',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.track_visit(request, response)
        return response

    def should_track(self, request, response):
        if request.method != 'GET':
            return False
        if response.status_code >= 400:
            return False
        if any(request.path.startswith(prefix) for prefix in self.IGNORED_PREFIXES):
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

    def track_visit(self, request, response):
        if not self.should_track(request, response):
            return

        user = request.user if request.user.is_authenticated else None
        SiteVisit.objects.create(
            user=user,
            visitor_key=self.get_visitor_key(request),
            path=request.path[:500],
            page_type=self.get_page_type(request),
            referrer=request.META.get('HTTP_REFERER', '')[:500],
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            ip_address=request.META.get('REMOTE_ADDR'),
            timestamp=timezone.now(),
        )
