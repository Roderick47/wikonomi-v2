from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import DashboardAccess, SiteVisit
from .views import build_dashboard_context


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
