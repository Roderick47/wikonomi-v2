import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import TemplateView

from core.models import Business, PriceReport, Product

from .mixins import DashboardAccessMixin
from .models import DashboardAccess, UserActivityLog, UserAnalytics


class AnalyticsDashboardView(DashboardAccessMixin, TemplateView):
    """Standalone analytics dashboard with role-specific data exposure."""

    template_name = 'analytics/dashboard.html'
    view_mode = DashboardAccess.DashboardRole.FOUNDER
    required_dashboard_roles = (
        DashboardAccess.DashboardRole.FOUNDER,
        DashboardAccess.DashboardRole.TEAM,
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_dashboard_context(context['view_mode']))
        return context


class TeamDashboardView(AnalyticsDashboardView):
    view_mode = DashboardAccess.DashboardRole.TEAM
    required_dashboard_roles = (DashboardAccess.DashboardRole.FOUNDER, DashboardAccess.DashboardRole.TEAM)


class InvestorDashboardView(AnalyticsDashboardView):
    view_mode = DashboardAccess.DashboardRole.INVESTOR
    required_dashboard_roles = (
        DashboardAccess.DashboardRole.FOUNDER,
        DashboardAccess.DashboardRole.INVESTOR,
    )


def pct(numerator, denominator):
    return round((numerator / denominator) * 100, 1) if denominator else 0


def build_dashboard_context(view_mode):
    now = timezone.now()
    start_30 = now - timedelta(days=30)
    start_7 = now - timedelta(days=7)

    total_users = User.objects.count()
    active_users_30 = UserAnalytics.objects.filter(last_activity_at__gte=start_30).count()
    new_users_30 = User.objects.filter(date_joined__gte=start_30).count()
    new_users_7 = User.objects.filter(date_joined__gte=start_7).count()
    total_price_reports = PriceReport.objects.count()
    total_products = Product.objects.count()
    total_businesses = Business.objects.count()

    activity_counts = dict(
        UserActivityLog.objects.filter(timestamp__gte=start_30)
        .values_list('activity_type')
        .annotate(total=Count('id'))
    )

    signup_rows = {
        row['day']: row['total']
        for row in User.objects.filter(date_joined__gte=start_30)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(total=Count('id'))
    }
    report_rows = {
        row['day']: row['total']
        for row in PriceReport.objects.filter(observed_at__gte=start_30)
        .annotate(day=TruncDate('observed_at'))
        .values('day')
        .annotate(total=Count('id'))
    }
    labels, signup_data, report_data = [], [], []
    for offset in range(29, -1, -1):
        day = (now - timedelta(days=offset)).date()
        labels.append(day.strftime('%b %-d'))
        signup_data.append(signup_rows.get(day, 0))
        report_data.append(report_rows.get(day, 0))

    top_products = list(
        Product.objects.annotate(report_count=Count('price_reports'))
        .filter(report_count__gt=0)
        .order_by('-report_count', 'name')[:5]
    )
    top_businesses = list(
        Business.objects.annotate(report_count=Count('price_reports'))
        .filter(report_count__gt=0)
        .order_by('-report_count', 'name')[:5]
    )

    context = {
        'title': f'{view_mode.title()} Analytics Dashboard',
        'total_users': total_users,
        'active_users_30': active_users_30,
        'new_users_30': new_users_30,
        'new_users_7': new_users_7,
        'active_rate': pct(active_users_30, total_users),
        'total_price_reports': total_price_reports,
        'total_products': total_products,
        'total_businesses': total_businesses,
        'avg_reports_per_user': round(total_price_reports / total_users, 1) if total_users else 0,
        'price_reports_30': PriceReport.objects.filter(observed_at__gte=start_30).count(),
        'activity_counts': activity_counts,
        'login_count': activity_counts.get('login', 0),
        'price_report_count': activity_counts.get('price_report', 0),
        'watchlist_count': activity_counts.get('watchlist_add', 0),
        'shopping_count': activity_counts.get('shopping_list_create', 0),
        'chart_labels': json.dumps(labels),
        'signup_data': json.dumps(signup_data),
        'report_data': json.dumps(report_data),
        'donut_labels': json.dumps(['Products', 'Businesses', 'Price reports']),
        'donut_data': json.dumps([total_products, total_businesses, total_price_reports]),
        'top_products': top_products,
        'top_businesses': top_businesses,
    }

    if view_mode != DashboardAccess.DashboardRole.INVESTOR:
        context.update({
            'recent_users': User.objects.order_by('-date_joined')[:10],
            'recent_activities': UserActivityLog.objects.select_related('user').order_by('-timestamp')[:15],
            'top_contributors': User.objects.annotate(report_count=Count('price_reports')).filter(report_count__gt=0).order_by('-report_count')[:10],
            'total_logins': UserAnalytics.objects.aggregate(total=Sum('login_count'))['total'] or 0,
        })
    else:
        context.update({
            'recent_users': [],
            'recent_activities': [],
            'top_contributors': [],
            'total_logins': None,
        })
    return context


analytics_dashboard = AnalyticsDashboardView.as_view()
team_dashboard = TeamDashboardView.as_view()
investor_dashboard = InvestorDashboardView.as_view()
