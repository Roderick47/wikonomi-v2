from django.db import migrations
import django_resized.forms


class Migration(migrations.Migration):
    dependencies = [('guides', '0003_step_and_tip_photos')]

    operations = [
        migrations.AddField(
            model_name='guide',
            name='photo',
            field=django_resized.forms.ResizedImageField(
                blank=True,
                force_format='JPEG',
                null=True,
                quality=82,
                size=[1600, 1000],
                upload_to='guide_photos/',
            ),
        ),
    ]
