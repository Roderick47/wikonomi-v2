from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('guides', '0004_guide_photo')]
    operations = [
        migrations.AddField(model_name='steptip', name='downvotes', field=models.PositiveIntegerField(default=0)),
        migrations.CreateModel(
            name='StepTipVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.SmallIntegerField(choices=[(1, 'Upvote'), (-1, 'Downvote')])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='guides.steptip')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guide_tip_votes', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name='steptipvote', constraint=models.UniqueConstraint(fields=('tip', 'user'), name='unique_tip_vote_per_user')),
    ]
