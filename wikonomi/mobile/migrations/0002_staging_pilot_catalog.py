"""Staging-only demo catalog for physical Android pilot QA.

Intentionally performs no writes except on the dedicated staging PostgreSQL
database when launched with the mobile_staging_settings module.
"""
import os

from django.db import migrations


def seed_staging_catalog(apps, schema_editor):
    from django.conf import settings

    if os.environ.get("DJANGO_SETTINGS_MODULE") != "wikonomi.mobile_staging_settings":
        return
    db = settings.DATABASES.get(schema_editor.connection.alias, {})
    if (
        db.get("ENGINE") != "django.db.backends.postgresql"
        or db.get("NAME") != "wikonomi_mobile_staging_db"
        or db.get("USER") != "wikonomi_mobile_staging_db_user"
    ):
        return

    Product = apps.get_model("core", "Product")
    Business = apps.get_model("core", "Business")
    BusinessBranch = apps.get_model("core", "BusinessBranch")
    alias = schema_editor.connection.alias

    Product.objects.using(alias).get_or_create(
        slug="wikonomi-demo-rice-1kg",
        defaults={"name": "Wikonomi Demo Rice 1kg"},
    )
    shop, _ = Business.objects.using(alias).get_or_create(
        slug="wikonomi-demo-shop",
        defaults={"name": "Wikonomi Demo Shop"},
    )
    BusinessBranch.objects.using(alias).get_or_create(
        canonical_business=shop,
        slug="wikonomi-demo-main",
        defaults={"name": "Main", "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("mobile", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(seed_staging_catalog, migrations.RunPython.noop),
    ]
