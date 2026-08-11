from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_profile_deletion_notifications_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='onboarding_completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='onboarding_dismissed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
