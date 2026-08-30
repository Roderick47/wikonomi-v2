from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0012_bulkimportsession_bulkimportrow_bulkimportimage_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='created_via',
            field=models.CharField(choices=[('web', 'Website'), ('bulk_import', 'Bulk import'), ('mcp', 'MCP')], db_index=True, default='web', max_length=20),
        ),
        migrations.AddField(model_name='product', name='ai_assisted', field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name='product', name='ai_provider', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='product', name='ai_model', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(
            model_name='product',
            name='ai_confidence',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True, validators=[MinValueValidator(0), MaxValueValidator(1)]),
        ),
        migrations.AddField(model_name='product', name='ai_source_note', field=models.TextField(blank=True)),
        migrations.AddField(
            model_name='pricereport',
            name='created_via',
            field=models.CharField(choices=[('web', 'Website'), ('bulk_import', 'Bulk import'), ('mcp', 'MCP')], db_index=True, default='web', max_length=20),
        ),
        migrations.AddField(model_name='pricereport', name='ai_assisted', field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name='pricereport', name='ai_provider', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='pricereport', name='ai_model', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(
            model_name='pricereport',
            name='ai_confidence',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True, validators=[MinValueValidator(0), MaxValueValidator(1)]),
        ),
        migrations.AddField(model_name='pricereport', name='ai_source_note', field=models.TextField(blank=True)),
        migrations.AddField(
            model_name='pricereport',
            name='mcp_idempotency_key',
            field=models.CharField(blank=True, max_length=160, null=True, unique=True),
        ),
        migrations.AddField(model_name='pricereportphoto', name='caption', field=models.CharField(blank=True, max_length=240)),
        migrations.AddField(model_name='pricereportphoto', name='content_hash', field=models.CharField(blank=True, db_index=True, max_length=64)),
        migrations.AddField(
            model_name='pricereportphoto',
            name='created_via',
            field=models.CharField(choices=[('web', 'Website'), ('bulk_import', 'Bulk import'), ('mcp', 'MCP')], db_index=True, default='web', max_length=20),
        ),
        migrations.AddField(
            model_name='pricereportphoto',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_price_report_photos', to=settings.AUTH_USER_MODEL),
        ),
    ]
