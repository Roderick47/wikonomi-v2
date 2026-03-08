from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta
import json

class UserAnalytics(models.Model):
    """Track user-level analytics and engagement metrics"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='analytics')
    
    # Signup metrics
    signup_date = models.DateTimeField(auto_now_add=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    first_price_report_at = models.DateTimeField(null=True, blank=True)
    
    # Engagement metrics
    total_price_reports = models.PositiveIntegerField(default=0)
    total_watchlist_additions = models.PositiveIntegerField(default=0)
    total_shopping_lists = models.PositiveIntegerField(default=0)
    last_login_at = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    
    # Activity tracking
    last_activity_at = models.DateTimeField(auto_now=True)
    is_active_user = models.BooleanField(default=False)  # Active in last 30 days
    
    class Meta:
        verbose_name_plural = "User Analytics"
    
    def __str__(self):
        return f"Analytics for {self.user.username}"
    
    def update_activity(self):
        """Update last activity and active status"""
        self.last_activity_at = timezone.now()
        thirty_days_ago = timezone.now() - timedelta(days=30)
        self.is_active_user = self.last_activity_at >= thirty_days_ago
        self.save(update_fields=['last_activity_at', 'is_active_user'])
    
    def days_since_signup(self):
        """Calculate days since user signup"""
        return (timezone.now() - self.signup_date).days
    
    def days_to_first_price_report(self):
        """Calculate days from signup to first price report"""
        if self.first_price_report_at:
            return (self.first_price_report_at - self.signup_date).days
        return None

class DailySignupMetrics(models.Model):
    """Track daily signup metrics"""
    date = models.DateField(unique=True)
    total_signups = models.PositiveIntegerField(default=0)
    verified_signups = models.PositiveIntegerField(default=0)
    price_contributor_signups = models.PositiveIntegerField(default=0)  # Users who submitted at least one price
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Daily Signup Metrics"
    
    def __str__(self):
        return f"Metrics for {self.date}"
    
    @classmethod
    def get_metrics_for_period(cls, start_date, end_date):
        """Get aggregated metrics for a date range"""
        metrics = cls.objects.filter(date__range=[start_date, end_date])
        return {
            'total_signups': metrics.aggregate(total=Count('total_signups'))['total'] or 0,
            'verified_signups': metrics.aggregate(total=Count('verified_signups'))['total'] or 0,
            'price_contributor_signups': metrics.aggregate(total=Count('price_contributor_signups'))['total'] or 0,
            'verification_rate': (metrics.aggregate(total=Count('verified_signups'))['total'] or 0) / max(1, metrics.aggregate(total=Count('total_signups'))['total'] or 1) * 100,
            'conversion_rate': (metrics.aggregate(total=Count('price_contributor_signups'))['total'] or 0) / max(1, metrics.aggregate(total=Count('total_signups'))['total'] or 1) * 100,
        }

class UserActivityLog(models.Model):
    """Log specific user activities for funnel analysis"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    activity_type = models.CharField(max_length=50)  # 'login', 'price_report', 'watchlist_add', 'shopping_list_create'
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)  # Store additional context
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'activity_type', 'timestamp']),
            models.Index(fields=['activity_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.activity_type} at {self.timestamp}"

# Signals to track user activities - temporarily disabled to prevent timezone issues
# @receiver(post_save, sender=User)
# def create_user_analytics(sender, instance, created, **kwargs):
#     """Create analytics record for new users"""
#     if created:
#         UserAnalytics.objects.create(user=instance, signup_date=timezone.now())
#         
#         # Update daily signup metrics
#         today = timezone.now().date()
#         metrics, created = DailySignupMetrics.objects.get_or_create(date=today)
#         metrics.total_signups += 1
#         metrics.save()

# @receiver(user_logged_in)
# def track_user_login(sender, request, user, **kwargs):
#     """Track user logins"""
#     analytics, created = UserAnalytics.objects.get_or_create(user=user)
#     analytics.last_login_at = timezone.now()
#     analytics.login_count += 1
#     analytics.update_activity()
#     
#     # Log activity
#     UserActivityLog.objects.create(
#         user=user,
#         activity_type='login',
#         metadata={'ip_address': request.META.get('REMOTE_ADDR', 'unknown')}
#     )

def track_price_report(user):
    """Track when user creates a price report"""
    analytics, created = UserAnalytics.objects.get_or_create(user=user)
    analytics.total_price_reports += 1
    
    # Track first price report
    if not analytics.first_price_report_at:
        analytics.first_price_report_at = timezone.now()
        
        # Update daily metrics for conversion tracking
        today = timezone.now().date()
        metrics, created = DailySignupMetrics.objects.get_or_create(date=today)
        if analytics.signup_date.date() == today:
            metrics.price_contributor_signups += 1
            metrics.save()
    
    analytics.update_activity()
    
    # Log activity
    UserActivityLog.objects.create(
        user=user,
        activity_type='price_report',
        metadata={'total_reports': analytics.total_price_reports}
    )

def track_watchlist_addition(user, product):
    """Track when user adds product to watchlist"""
    analytics, created = UserAnalytics.objects.get_or_create(user=user)
    analytics.total_watchlist_additions += 1
    analytics.update_activity()
    
    # Log activity
    UserActivityLog.objects.create(
        user=user,
        activity_type='watchlist_add',
        metadata={'product_id': product.id, 'product_name': product.name}
    )

def track_shopping_list_creation(user):
    """Track when user creates a shopping list"""
    analytics, created = UserAnalytics.objects.get_or_create(user=user)
    analytics.total_shopping_lists += 1
    analytics.update_activity()
    
    # Log activity
    UserActivityLog.objects.create(
        user=user,
        activity_type='shopping_list_create',
        metadata={'total_lists': analytics.total_shopping_lists}
    )

def track_email_verification(user):
    """Track when user verifies email"""
    analytics, created = UserAnalytics.objects.get_or_create(user=user)
    analytics.email_verified_at = timezone.now()
    analytics.save()
    
    # Update daily metrics
    signup_date = analytics.signup_date.date()
    metrics, created = DailySignupMetrics.objects.get_or_create(date=signup_date)
    metrics.verified_signups += 1
    metrics.save()
