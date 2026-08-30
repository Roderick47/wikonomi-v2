import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MCPOAuthClient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_id', models.CharField(max_length=255, unique=True)),
                ('client_name', models.CharField(blank=True, max_length=255)),
                ('metadata', models.JSONField(default=dict)),
                ('encrypted_client_secret', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='MCPUserAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('owner', 'Owner'), ('staff', 'Staff'), ('trusted', 'Trusted contributor'), ('reader', 'Read only')], default='reader', max_length=16)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mcp_access', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'MCP user access', 'verbose_name_plural': 'MCP user access'},
        ),
        migrations.CreateModel(
            name='MCPAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('correlation_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
                ('tool_name', models.CharField(db_index=True, max_length=120)),
                ('client_id', models.CharField(blank=True, max_length=255)),
                ('role', models.CharField(blank=True, max_length=16)),
                ('status', models.CharField(choices=[('started', 'Started'), ('succeeded', 'Succeeded'), ('denied', 'Denied'), ('failed', 'Failed')], db_index=True, default='started', max_length=16)),
                ('arguments', models.JSONField(blank=True, default=dict)),
                ('response_summary', models.JSONField(blank=True, default=dict)),
                ('error_message', models.TextField(blank=True)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mcp_audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-started_at'],
                'indexes': [
                    models.Index(fields=['user', '-started_at'], name='mcp_audit_user_time_idx'),
                    models.Index(fields=['tool_name', 'status', '-started_at'], name='mcp_audit_tool_time_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='MCPOAuthAuthorizationRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('redirect_uri', models.URLField(max_length=2048)),
                ('redirect_uri_provided_explicitly', models.BooleanField(default=True)),
                ('state', models.TextField(blank=True)),
                ('scopes', models.JSONField(default=list)),
                ('code_challenge', models.CharField(max_length=255)),
                ('resource', models.URLField(blank=True, max_length=2048)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authorization_requests', to='mcp_server.mcpoauthclient')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='MCPOAuthAuthorizationCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code_hash', models.CharField(max_length=64, unique=True)),
                ('scopes', models.JSONField(default=list)),
                ('code_challenge', models.CharField(max_length=255)),
                ('redirect_uri', models.URLField(max_length=2048)),
                ('redirect_uri_provided_explicitly', models.BooleanField(default=True)),
                ('resource', models.URLField(blank=True, max_length=2048)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authorization_codes', to='mcp_server.mcpoauthclient')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mcp_authorization_codes', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='MCPOAuthToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('token_type', models.CharField(choices=[('access', 'Access token'), ('refresh', 'Refresh token')], max_length=12)),
                ('scopes', models.JSONField(default=list)),
                ('resource', models.URLField(blank=True, max_length=2048)),
                ('family_id', models.UUIDField(db_index=True, default=uuid.uuid4)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tokens', to='mcp_server.mcpoauthclient')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mcp_tokens', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['token_type', 'expires_at'], name='mcp_token_type_exp_idx'),
                    models.Index(fields=['client', 'user', 'revoked_at'], name='mcp_token_actor_idx'),
                ],
            },
        ),
    ]
