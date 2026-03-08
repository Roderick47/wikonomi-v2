from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg
from datetime import timedelta, date
from .models import UserAnalytics, DailySignupMetrics, UserActivityLog
import json

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def analytics_dashboard(request):
    """Analytics dashboard for superusers only"""
    
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
    
    # Top contributors
    top_contributors = UserAnalytics.objects.filter(total_price_reports__gt=0).order_by('-total_price_reports')[:10]
    
    # Recent activity
    recent_activities = UserActivityLog.objects.select_related('user').order_by('-timestamp')[:10]
    
    context = {
        'title': 'Analytics Dashboard',
        
        # User metrics
        'total_users': total_users,
        'active_users_30': active_users_30,
        'new_users_30': new_users_30,
        'new_users_7': new_users_7,
        'active_rate': round((active_users_30 / max(1, total_users)) * 100, 1),
        
        # Engagement
        'total_price_reports': total_price_reports,
        'avg_reports_per_user': round(avg_reports_per_user, 1),
        'total_logins': total_logins,
        'avg_logins_per_user': round(avg_logins_per_user, 1),
        
        # Conversion funnel
        'total_signups_30': total_signups_30,
        'verified_30': verified_30,
        'contributors_30': contributors_30,
        'verification_rate_30': round((verified_30 / max(1, total_signups_30)) * 100, 1),
        'conversion_rate_30': round((contributors_30 / max(1, total_signups_30)) * 100, 1),
        
        # Activity breakdown
        'login_count': login_count,
        'price_report_count': price_report_count,
        'watchlist_count': watchlist_count,
        'shopping_count': shopping_count,
        
        # Chart data
        'signup_labels': json.dumps(signup_labels),
        'signup_data': json.dumps(signup_data),
        'verified_data': json.dumps(verified_data),
        
        # Additional data
        'top_contributors': top_contributors,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'analytics/dashboard.html', context)
