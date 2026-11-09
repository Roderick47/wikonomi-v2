from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0013_mcp_ai_provenance")]

    operations = [
        migrations.AddField(
            model_name="pricereport",
            name="country_code",
            field=models.CharField(max_length=2, db_index=True, default="PG"),
        ),
        migrations.AddField(
            model_name="businessbranch",
            name="country_code",
            field=models.CharField(max_length=2, db_index=True, default="PG"),
        ),
        migrations.AddField(
            model_name="business",
            name="country_code",
            field=models.CharField(max_length=2, db_index=True, default="PG"),
        ),
    ]
