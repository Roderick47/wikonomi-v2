# Generated for Wikonomi's additive promotions layer.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('categories', '0001_initial'),
        ('core', '0013_mcp_ai_provenance'),
    ]

    operations = [
        migrations.CreateModel(
            name='Promotion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180)),
                ('kind', models.CharField(choices=[('sale', 'Sale / special'), ('clearance', 'Clearance'), ('event', 'Promotional event')], db_index=True, default='sale', max_length=20)),
                ('deal_type', models.CharField(choices=[('percent', 'Percentage off'), ('amount_off', 'Kina amount off'), ('fixed_price', 'Special price'), ('multibuy', 'Multi-buy / buy X get Y'), ('other', 'Other offer')], default='percent', max_length=20)),
                ('scope', models.CharField(choices=[('storewide', 'Entire store'), ('category', 'Category / subcategory'), ('product', 'Specific product')], db_index=True, default='storewide', max_length=20)),
                ('discount_value', models.DecimalField(blank=True, decimal_places=2, help_text='Percent or kina amount, depending on deal type.', max_digits=12, null=True)),
                ('special_price', models.DecimalField(blank=True, decimal_places=2, help_text='Used for a directly observed special price.', max_digits=12, null=True)),
                ('description', models.TextField(blank=True)),
                ('terms', models.TextField(blank=True, help_text='Exclusions or conditions shown on the promotion.')),
                ('start_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('end_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('evidence', models.ImageField(blank=True, null=True, upload_to='promotions/evidence/%Y/%m/')),
                ('source', models.CharField(choices=[('community', 'Community report'), ('business', 'Business-posted'), ('admin', 'Wikonomi verified/admin')], db_index=True, default='community', max_length=20)),
                ('is_verified', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotions', to='core.business')),
                ('business_branch', models.ForeignKey(blank=True, help_text='Optional: limit this promotion to one branch/location.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='promotions', to='core.businessbranch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reported_promotions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-start_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PromotionTarget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='promotion_targets', to='categories.category')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='promotion_targets', to='core.product')),
                ('promotion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='targets', to='promotions.promotion')),
                ('subcategory', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='promotion_targets', to='categories.subcategory')),
            ],
            options={
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.CreateModel(
            name='PromotionConfirmation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_still_active', models.BooleanField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('promotion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='confirmations', to='promotions.promotion')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotion_confirmations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='promotionconfirmation',
            constraint=models.UniqueConstraint(fields=('promotion', 'user'), name='unique_promotion_confirmation_per_user'),
        ),
    ]
