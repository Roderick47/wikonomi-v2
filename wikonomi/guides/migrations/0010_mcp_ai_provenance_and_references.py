from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('guides', '0009_guideanswer_upvote_count_and_ordering'),
    ]

    operations = [
        migrations.AddField(
            model_name='guide',
            name='created_via',
            field=models.CharField(choices=[('web', 'Website'), ('mcp', 'MCP')], db_index=True, default='web', max_length=20),
        ),
        migrations.AddField(model_name='guide', name='ai_assisted', field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name='guide', name='ai_provider', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='guide', name='ai_model', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(
            model_name='guide',
            name='ai_confidence',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True, validators=[MinValueValidator(0), MaxValueValidator(1)]),
        ),
        migrations.AddField(model_name='guide', name='ai_source_note', field=models.TextField(blank=True)),
        migrations.AddField(
            model_name='guide',
            name='mcp_idempotency_key',
            field=models.CharField(blank=True, max_length=160, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='guideversion',
            name='created_via',
            field=models.CharField(choices=[('web', 'Website'), ('mcp', 'MCP')], db_index=True, default='web', max_length=20),
        ),
        migrations.AddField(model_name='guideversion', name='ai_assisted', field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name='guideversion', name='ai_provider', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='guideversion', name='ai_model', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(
            model_name='guideversion',
            name='ai_confidence',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True, validators=[MinValueValidator(0), MaxValueValidator(1)]),
        ),
        migrations.AddField(model_name='guideversion', name='ai_source_note', field=models.TextField(blank=True)),
        migrations.CreateModel(
            name='GuideReference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('url', models.URLField(max_length=2048)),
                ('publisher', models.CharField(blank=True, max_length=180)),
                ('accessed_at', models.DateField(blank=True, null=True)),
                ('version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='references', to='guides.guideversion')),
            ],
            options={'ordering': ['id']},
        ),
    ]
