from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0013_mcp_ai_provenance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductIdentity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('brand', models.CharField(blank=True, db_index=True, max_length=120)),
                ('variant', models.CharField(blank=True, max_length=160)),
                ('package_quantity', models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ('package_unit', models.CharField(blank=True, choices=[('g', 'Gram'), ('kg', 'Kilogram'), ('ml', 'Millilitre'), ('l', 'Litre'), ('each', 'Each'), ('m', 'Metre'), ('cm', 'Centimetre'), ('other', 'Other')], db_index=True, max_length=16)),
                ('pack_count', models.PositiveIntegerField(blank=True, null=True)),
                ('barcode', models.CharField(blank=True, db_index=True, max_length=64)),
                ('normalized_barcode', models.CharField(blank=True, db_index=True, max_length=64)),
                ('identity_signature', models.CharField(blank=True, db_index=True, max_length=512)),
                ('source', models.CharField(choices=[('inferred', 'Inferred from name'), ('web', 'Website'), ('bulk_import', 'Bulk import'), ('mcp', 'MCP'), ('manual', 'Manual review')], db_index=True, default='inferred', max_length=20)),
                ('confidence', models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='identity', to='core.product')),
            ],
        ),
        migrations.CreateModel(
            name='ProductDuplicateCandidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('similarity_score', models.DecimalField(decimal_places=4, max_digits=5)),
                ('match_basis', models.CharField(max_length=80)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('pending', 'Pending review'), ('confirmed', 'Confirmed duplicate'), ('rejected', 'Not a duplicate')], db_index=True, default='pending', max_length=16)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('candidate_product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='duplicate_candidates_received', to='core.product')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_product_duplicates', to=settings.AUTH_USER_MODEL)),
                ('source_product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='duplicate_candidates_started', to='core.product')),
            ],
            options={
                'ordering': ['status', '-similarity_score', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='productidentity',
            index=models.Index(fields=['brand', 'package_unit'], name='catalog_id_brand_unit_idx'),
        ),
        migrations.AddIndex(
            model_name='productidentity',
            index=models.Index(fields=['normalized_barcode'], name='catalog_id_barcode_idx'),
        ),
        migrations.AddIndex(
            model_name='productidentity',
            index=models.Index(fields=['identity_signature'], name='catalog_id_signature_idx'),
        ),
        migrations.AddIndex(
            model_name='productduplicatecandidate',
            index=models.Index(fields=['status', '-similarity_score'], name='catalog_dup_status_score_idx'),
        ),
        migrations.AddConstraint(
            model_name='productduplicatecandidate',
            constraint=models.UniqueConstraint(fields=('source_product', 'candidate_product'), name='unique_product_duplicate_candidate_pair'),
        ),
        migrations.AddConstraint(
            model_name='productduplicatecandidate',
            constraint=models.CheckConstraint(condition=~models.Q(source_product=models.F('candidate_product')), name='product_duplicate_candidate_not_self'),
        ),
    ]
