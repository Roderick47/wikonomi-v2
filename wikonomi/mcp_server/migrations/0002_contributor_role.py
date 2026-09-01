from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('mcp_server', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='mcpuseraccess',
            name='role',
            field=models.CharField(
                choices=[
                    ('owner', 'Owner'),
                    ('staff', 'Staff'),
                    ('trusted', 'Trusted contributor'),
                    ('contributor', 'Contributor'),
                    ('reader', 'Read only'),
                ],
                default='reader',
                max_length=16,
            ),
        ),
    ]
