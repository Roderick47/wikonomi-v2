# Generated migration to fix timezone issues in existing analytics data

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_analyticsdashboardproxy_and_more'),
    ]

    operations = [
        migrations.RunPython(
            code=fix_user_analytics_timezones,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.RunPython(
            code=fix_activity_log_timezones,
            reverse_code=migrations.RunPython.noop
        ),
    ]

def fix_user_analytics_timezones(apps, schema_editor):
    """Fix naive datetimes in existing UserAnalytics records"""
    from analytics.models import UserAnalytics
    
    # Update records with naive signup_date
    UserAnalytics.objects.filter(signup_date__isnull=False).update(
        signup_date=django.utils.timezone.make_aware(
            models.F('signup_date')
        )
    )
    
    # Update records with naive email_verified_at
    UserAnalytics.objects.filter(email_verified_at__isnull=False).update(
        email_verified_at=django.utils.timezone.make_aware(
            models.F('email_verified_at')
        )
    )
    
    # Update records with naive first_price_report_at
    UserAnalytics.objects.filter(first_price_report_at__isnull=False).update(
        first_price_report_at=django.utils.timezone.make_aware(
            models.F('first_price_report_at')
        )
    )
    
    # Update records with naive last_login_at
    UserAnalytics.objects.filter(last_login_at__isnull=False).update(
        last_login_at=django.utils.timezone.make_aware(
            models.F('last_login_at')
        )
    )

def fix_activity_log_timezones(apps, schema_editor):
    """Fix naive timestamps in existing UserActivityLog records"""
    from analytics.models import UserActivityLog
    
    # Update records with naive timestamps
    UserActivityLog.objects.filter(timestamp__isnull=False).update(
        timestamp=django.utils.timezone.make_aware(
            models.F('timestamp')
        )
    )
