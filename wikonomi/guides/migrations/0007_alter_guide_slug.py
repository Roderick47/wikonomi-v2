from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('guides', '0006_guide_questions_and_deletion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guide',
            name='slug',
            field=models.SlugField(max_length=255, unique=True),
        ),
    ]
