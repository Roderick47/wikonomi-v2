# Generated manually for multi-photo price reports

from django.db import migrations, models
import django.db.models.deletion
import django_resized.forms


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_business_business_subcategory_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PriceReportPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', django_resized.forms.ResizedImageField(crop=None, force_format='JPEG', keep_meta=True, quality=75, scale=None, size=[1000, 1000], upload_to='price_report_photos/')),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('price_report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='core.pricereport')),
            ],
            options={
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
