from django.contrib import admin
from django.db.models import Count, Avg
from django.utils.html import format_html
from .models import UserAnalytics, DailySignupMetrics, UserActivityLog

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
            'fields': ('email_verified_at', 'first_price_report_at')
        }),
        ('Engagement Metrics', {
            'fields': ('total_price_reports', 'total_watchlist_additions', 'total_shopping_lists', 'login_count', 'last_login_at')
        }),
    )
    
    def days_since_signup(self, obj):
        days = (obj.signup_date and (timezone.now() - obj.signup_date).days) or 0
        color = 'green' if days < 30 else 'orange' if days < 90 else 'red'
        return format_html(f'<span style="color: {color};">{days} days</span>')
    days_since_signup.short_description = 'Days Since Signup'

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
