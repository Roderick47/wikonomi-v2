import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('guides', '0005_steptip_downvotes_steptipvote'),
    ]

    operations = [
        migrations.AddField(
            model_name='guide',
            name='marked_for_deletion',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='guide',
            name='marked_for_deletion_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='guide',
            name='deletion_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='guide',
            name='marked_for_deletion_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marked_guides_for_deletion', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='guide',
            name='deletion_votes',
            field=models.ManyToManyField(blank=True, related_name='confirmed_guide_deletions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='GuideQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(max_length=1200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='guide_questions', to=settings.AUTH_USER_MODEL)),
                ('guide', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='guides.guide')),
                ('step', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions', to='guides.step')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='GuideAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(max_length=2000)),
                ('is_accepted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='guide_answers', to=settings.AUTH_USER_MODEL)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='guides.guidequestion')),
            ],
            options={'ordering': ['-is_accepted', 'created_at']},
        ),
    ]
