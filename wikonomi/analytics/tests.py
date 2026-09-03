from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.db import DatabaseError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .models import DashboardAccess, SiteVisit
from .middleware import SiteVisitTrackingMiddleware
from .views import build_dashboard_context


class SiteVisitTrackingMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _anonymous_request(self, path='/', user_agent='Mozilla/5.0'):
        request = self.factory.get(path, HTTP_USER_AGENT=user_agent)
        request.user = AnonymousUser()
        request.session = SimpleNamespace(session_key='test-session')
        return request

    def test_database_error_does_not_replace_successful_response(self):
        request = self._anonymous_request()
        response = HttpResponse('ok')
        middleware = SiteVisitTrackingMiddleware(lambda incoming_request: response)

        with patch.object(
            middleware,
            'track_visit',
            side_effect=DatabaseError('not ready'),
        ):
            result = middleware(request)

        self.assertIs(result, response)
        self.assertEqual(result.status_code, 200)

    @override_settings(SITE_VISIT_ANALYTICS_ENABLED=False)
    def test_disabled_analytics_does_not_write_site_visit(self):
        request = self._anonymous_request()
        response = HttpResponse('ok', content_type='text/html')
        middleware = SiteVisitTrackingMiddleware(lambda incoming_request: response)

        with patch('analytics.middleware.SiteVisit.objects.create') as create_visit:
            middleware.track_visit(request, response)

        create_visit.assert_not_called()

    @override_settings(SITE_VISIT_ANALYTICS_ENABLED=True)
    def test_bot_user_agent_does_not_write_site_visit(self):
        request = self._anonymous_request(
            user_agent='Mozilla/5.0 (compatible; PerplexityBot/1.0)',
        )
        response = HttpResponse('ok', content_type='text/html')
        middleware = SiteVisitTrackingMiddleware(lambda incoming_request: response)

        with patch('analytics.middleware.SiteVisit.objects.create') as create_visit:
            middleware.track_visit(request, response)

        create_visit.assert_not_called()

    @override_settings(
        SITE_VISIT_ANALYTICS_ENABLED=True,
        SITE_VISIT_MIN_INTERVAL_SECONDS=60,
    )
    def test_human_page_visits_are_rate_limited_in_process_memory(self):
        request = self._anonymous_request()
        response = HttpResponse('ok', content_type='text/html')
        middleware = SiteVisitTrackingMiddleware(lambda incoming_request: response)

        with patch('analytics.middleware.SiteVisit.objects.create') as create_visit:
            middleware.track_visit(request, response)
            middleware.track_visit(request, response)

        self.assertEqual(create_visit.call_count, 1)


class FounderVisitorMetricsTest(TestCase):
    def test_founder_context_includes_visitor_windows(self):
        user = User.objects.create_user(username='visitor', password='testpass')
        now = timezone.now()
        SiteVisit.objects.create(
            user=None,
            visitor_key='anon:one',
            path='/about/',
            page_type=SiteVisit.PageType.ABOUT,
            timestamp=now - timedelta(hours=2),
        )
        SiteVisit.objects.create(
            user=user,
            visitor_key=f'user:{user.pk}',
            path='/price/1/',
            page_type=SiteVisit.PageType.PRICE_DETAIL,
            timestamp=now - timedelta(days=2),
        )
        SiteVisit.objects.create(
            user=None,
            visitor_key='anon:old',
            path='/',
            page_type=SiteVisit.PageType.PAGE,
            timestamp=now - timedelta(days=120),
        )

        context = build_dashboard_context(DashboardAccess.DashboardRole.FOUNDER)
        windows = {row['label']: row for row in context['founder_visitor_windows']}

        self.assertEqual(windows['24 hours']['unique_visitors'], 1)
        self.assertEqual(windows['24 hours']['anonymous_visitors'], 1)
        self.assertEqual(windows['24 hours']['about_visits'], 1)
        self.assertEqual(windows['3 days']['unique_visitors'], 2)
        self.assertEqual(windows['3 days']['signed_in_visitors'], 1)
        self.assertEqual(windows['3 days']['price_clicks'], 1)
        self.assertEqual(windows['3 months']['unique_visitors'], 2)

    def test_investor_context_does_not_include_founder_visitor_windows(self):
        context = build_dashboard_context(DashboardAccess.DashboardRole.INVESTOR)
        self.assertEqual(context['founder_visitor_windows'], [])
