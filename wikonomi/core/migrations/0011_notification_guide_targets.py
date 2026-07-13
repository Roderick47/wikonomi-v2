from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0010_pricereport_duplicate_trust_votes_and_more')]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='target_url',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('general', 'General'),
                    ('comment', 'Comment'),
                    ('reply', 'Reply'),
                    ('comment_like', 'Comment Like'),
                    ('deletion_mark', 'Deletion Mark'),
                    ('guide_question', 'Guide Question'),
                    ('guide_answer', 'Guide Answer'),
                    ('guide_deletion', 'Guide Deletion'),
                ],
                default='general',
                max_length=32,
            ),
        ),
    ]
