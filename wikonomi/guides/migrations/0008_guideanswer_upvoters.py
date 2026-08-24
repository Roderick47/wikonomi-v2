from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('guides', '0007_alter_guide_slug'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='guideanswer',
            name='upvoters',
            field=models.ManyToManyField(
                blank=True,
                related_name='upvoted_guide_answers',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
