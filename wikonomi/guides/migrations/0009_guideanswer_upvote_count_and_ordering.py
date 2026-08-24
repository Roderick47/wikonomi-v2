from django.db import migrations, models


def populate_upvote_counts(apps, schema_editor):
    GuideAnswer = apps.get_model('guides', 'GuideAnswer')
    through = GuideAnswer.upvoters.through
    for answer in GuideAnswer.objects.all().iterator():
        count = through.objects.filter(guideanswer_id=answer.pk).count()
        GuideAnswer.objects.filter(pk=answer.pk).update(upvote_count=count)


class Migration(migrations.Migration):

    dependencies = [
        ('guides', '0008_guideanswer_upvoters'),
    ]

    operations = [
        migrations.AddField(
            model_name='guideanswer',
            name='upvote_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(populate_upvote_counts, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='guideanswer',
            options={'ordering': ['-is_accepted', '-upvote_count', 'created_at']},
        ),
    ]
