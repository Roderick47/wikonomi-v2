from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comments', '0002_backfill_from_core_comment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comment',
            name='body',
            field=models.TextField(max_length=2000),
        ),
    ]
