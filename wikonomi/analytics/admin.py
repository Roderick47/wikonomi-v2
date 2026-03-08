from django.contrib import admin
from django.db.models import Count, Avg, Q, F
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.db.models import DateTimeField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from datetime import timedelta, date
from .models import UserAnalytics, DailySignupMetrics, UserActivityLog
import json

@admin.register(UserAnalytics)
class UserAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['user', 'signup_date', 'total_price_reports', 'login_count', 'is_active_user', 'days_since_signup']
    list_filter = ['is_active_user', 'signup_date', 'email_verified_at', 'first_price_report_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user', 'signup_date', 'last_activity_at']
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'signup_date', 'last_activity_at', 'is_active_user')
        }),
        ('Signup Funnel', {
            'fields': ('email_verified_at', 'first_price_report_at', 'days_to_first_price_report')
        }),
        ('Engagement Metrics', {
            'fields': ('total_price_reports', 'total_watchlist_additions', 'total_shopping_lists', 'login_count', 'last_login_at')
        }),
    )
    
    def days_since_signup(self, obj):
        days = obj.days_since_signup()
        color = 'green' if days < 30 else 'orange' if days < 90 else 'red'
        return format_html(f'<span style="color: {color};">{days} days</span>')
    days_since_signup.short_description = 'Days Since Signup'
    
    def days_to_first_price_report(self, obj):
        days = obj.days_to_first_price_report()
        if days is None:
            return format_html('<span style="color: red;">No price reports</span>')
        color = 'green' if days < 7 else 'orange' if days < 30 else 'red'
        return format_html(f'<span style="color: {color};">{days} days</span>')
    days_to_first_price_report.short_description = 'Time to First Report'

@admin.register(DailySignupMetrics)
class DailySignupMetricsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_signups', 'verified_signups', 'price_contributor_signups', 'verification_rate', 'conversion_rate']
    list_filter = ['date']
    date_hierarchy = 'date'
    
    def verification_rate(self, obj):
        if obj.total_signups == 0:
            return "0%"
        rate = (obj.verified_signups / obj.total_signups) * 100
        color = 'green' if rate > 80 else 'orange' if rate > 50 else 'red'
        return format_html(f'<span style="color: {color};">{rate:.1f}%</span>')
    verification_rate.short_description = 'Email Verification Rate'
    
    def conversion_rate(self, obj):
        if obj.total_signups == 0:
            return "0%"
        rate = (obj.price_contributor_signups / obj.total_signups) * 100
        color = 'green' if rate > 50 else 'orange' if rate > 25 else 'red'
        return format_html(f'<span style="color: {color};">{rate:.1f}%</span>')
    conversion_rate.short_description = 'Price Contributor Rate'

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity_type', 'timestamp', 'metadata_preview']
    list_filter = ['activity_type', 'timestamp']
    search_fields = ['user__username']
    readonly_fields = ['user', 'activity_type', 'timestamp', 'metadata']
    
    def metadata_preview(self, obj):
        if not obj.metadata:
            return "-"
        preview = str(obj.metadata)[:100]
        if len(str(obj.metadata)) > 100:
            preview += "..."
        return preview
    metadata_preview.short_description = 'Metadata'

class AnalyticsDashboardAdmin(admin.ModelAdmin):
    """Custom admin dashboard for analytics"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics-dashboard/', self.admin_site.admin_view(self.analytics_dashboard), name='analytics_dashboard'),
        ]
        return custom_urls + urls
    
    def analytics_dashboard(self, request):
        """Main analytics dashboard view"""
        
        # Time periods
        today = date.today()
        last_30_days = today - timedelta(days=30)
        last_7_days = today - timedelta(days=7)
        
        # User signup metrics
        total_users = UserAnalytics.objects.count()
        active_users_30 = UserAnalytics.objects.filter(is_active_user=True).count()
        new_users_30 = UserAnalytics.objects.filter(signup_date__gte=last_30_days).count()
        new_users_7 = UserAnalytics.objects.filter(signup_date__gte=last_7_days).count()
        
        # Daily signup trends
        daily_signups = DailySignupMetrics.objects.filter(date__gte=last_30_days).order_by('date')
        signup_labels = [d.date.strftime('%m/%d') for d in daily_signups]
        signup_data = [d.total_signups for d in daily_signups]
        verified_data = [d.verified_signups for d in daily_signups]
        
        # Engagement metrics
        total_price_reports = UserAnalytics.objects.aggregate(total=Count('total_price_reports'))['total'] or 0
        avg_reports_per_user = UserAnalytics.objects.aggregate(avg=Avg('total_price_reports'))['avg'] or 0
        total_logins = UserAnalytics.objects.aggregate(total=Count('login_count'))['total'] or 0
        avg_logins_per_user = UserAnalytics.objects.aggregate(avg=Avg('login_count'))['avg'] or 0
        
        # Conversion funnel
        total_signups_30 = DailySignupMetrics.objects.filter(date__gte=last_30_days).aggregate(total=Count('total_signups'))['total'] or 0
        verified_30 = DailySignupMetrics.objects.filter(date__gte=last_30_days).aggregate(total=Count('verified_signups'))['total'] or 0
        contributors_30 = DailySignupMetrics.objects.filter(date__gte=last_30_days).aggregate(total=Count('price_contributor_signups'))['total'] or 0
        
        # Activity breakdown
        login_count = UserActivityLog.objects.filter(activity_type='login', timestamp__gte=last_30_days).count()
        price_report_count = UserActivityLog.objects.filter(activity_type='price_report', timestamp__gte=last_30_days).count()
        watchlist_count = UserActivityLog.objects.filter(activity_type='watchlist_add', timestamp__gte=last_30_days).count()
        shopping_count = UserActivityLog.objects.filter(activity_type='shopping_list_create', timestamp__gte=last_30_days).count()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Analytics Dashboard',
            
            # User metrics
            'total_users': total_users,
            'active_users_30': active_users_30,
            'new_users_30': new_users_30,
            'new_users_7': new_users_7,
            'active_rate': (active_users_30 / max(1, total_users)) * 100,
            
            # Engagement
            'total_price_reports': total_price_reports,
            'avg_reports_per_user': round(avg_reports_per_user, 1),
            'total_logins': total_logins,
            'avg_logins_per_user': round(avg_logins_per_user, 1),
            
            # Conversion funnel
            'total_signups_30': total_signups_30,
            'verified_30': verified_30,
            'contributors_30': contributors_30,
            'verification_rate_30': (verified_30 / max(1, total_signups_30)) * 100,
            'conversion_rate_30': (contributors_30 / max(1, total_signups_30)) * 100,
            
            # Activity breakdown
            'login_count': login_count,
            'price_report_count': price_report_count,
            'watchlist_count': watchlist_count,
            'shopping_count': shopping_count,
            
            # Chart data
            'signup_labels': json.dumps(signup_labels),
            'signup_data': json.dumps(signup_data),
            'verified_data': json.dumps(verified_data),
            
            # Recent activity
            'recent_activities': UserActivityLog.objects.select_related('user').order_by('-timestamp')[:10],
        }
        
        return render(request, 'admin/analytics_dashboard.html', context)

# Register the dashboard with a dummy model
from django.contrib.auth.models import User
class AnalyticsDashboardProxy(User):
    class Meta:
        proxy = True
        verbose_name = "Analytics Dashboard"
        verbose_name_plural = "Analytics Dashboard"

admin.site.register(AnalyticsDashboardProxy, AnalyticsDashboardAdmin)
