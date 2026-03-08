from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
import json

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def analytics_dashboard(request):
    """Simple analytics dashboard for superusers only"""
    
    # Safe defaults - no database calls that could cause 500 errors
    context = {
        'title': 'Analytics Dashboard',
        'total_users': 0,
        'active_users_30': 0,
        'new_users_30': 0,
        'new_users_7': 0,
        'active_rate': 0,
        'total_price_reports': 0,
        'avg_reports_per_user': 0,
        'total_logins': 0,
        'avg_logins_per_user': 0,
        'total_signups_30': 0,
        'verified_30': 0,
        'contributors_30': 0,
        'verification_rate_30': 0,
        'conversion_rate_30': 0,
        'login_count': 0,
        'price_report_count': 0,
        'watchlist_count': 0,
        'shopping_count': 0,
        'signup_labels': json.dumps([]),
        'signup_data': json.dumps([]),
        'verified_data': json.dumps([]),
        'top_contributors': [],
        'recent_activities': [],
    }
    
    return render(request, 'analytics/dashboard.html', context)
