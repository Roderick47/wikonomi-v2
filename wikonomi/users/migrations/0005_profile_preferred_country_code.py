from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0004_profile_onboarding_state")]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="preferred_country_code",
            field=models.CharField(max_length=2, blank=True, default=""),
        ),
    ]
