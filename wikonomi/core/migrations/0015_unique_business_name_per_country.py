from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0014_market_country_codes")]

    operations = [
        migrations.AlterField(
            model_name="business",
            name="name",
            field=models.CharField(max_length=255),
        ),
        migrations.AddConstraint(
            model_name="business",
            constraint=models.UniqueConstraint(
                fields=("country_code", "name"),
                name="uniq_business_name_country",
            ),
        ),
    ]
