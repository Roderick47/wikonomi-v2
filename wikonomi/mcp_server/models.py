import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class MCPUserAccess(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        STAFF = 'staff', 'Staff'
        TRUSTED = 'trusted', 'Trusted contributor'
        CONTRIBUTOR = 'contributor', 'Contributor'
        READER = 'reader', 'Read only'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mcp_access',
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.READER)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'MCP user access'
        verbose_name_plural = 'MCP user access'

    def __str__(self):
        state = 'active' if self.is_active else 'disabled'
        return f'{self.user} — {self.get_role_display()} ({state})'


class MCPOAuthClient(models.Model):
    """Dynamically registered MCP OAuth client metadata."""

    client_id = models.CharField(max_length=255, unique=True)
    client_name = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict)
    encrypted_client_secret = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.client_name or self.client_id


class MCPOAuthAuthorizationRequest(models.Model):
    """Short-lived browser approval request created by the OAuth authorize step."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(MCPOAuthClient, on_delete=models.CASCADE, related_name='authorization_requests')
    redirect_uri = models.URLField(max_length=2048)
    redirect_uri_provided_explicitly = models.BooleanField(default=True)
    state = models.TextField(blank=True)
    scopes = models.JSONField(default=list)
    code_challenge = models.CharField(max_length=255)
    resource = models.URLField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()


class MCPOAuthAuthorizationCode(models.Model):
    code_hash = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(MCPOAuthClient, on_delete=models.CASCADE, related_name='authorization_codes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mcp_authorization_codes')
    scopes = models.JSONField(default=list)
    code_challenge = models.CharField(max_length=255)
    redirect_uri = models.URLField(max_length=2048)
    redirect_uri_provided_explicitly = models.BooleanField(default=True)
    resource = models.URLField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()


class MCPOAuthToken(models.Model):
    class Type(models.TextChoices):
        ACCESS = 'access', 'Access token'
        REFRESH = 'refresh', 'Refresh token'

    token_hash = models.CharField(max_length=64, unique=True)
    token_type = models.CharField(max_length=12, choices=Type.choices)
    client = models.ForeignKey(MCPOAuthClient, on_delete=models.CASCADE, related_name='tokens')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mcp_tokens')
    scopes = models.JSONField(default=list)
    resource = models.URLField(max_length=2048, blank=True)
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token_type', 'expires_at'], name='mcp_token_type_exp_idx'),
            models.Index(fields=['client', 'user', 'revoked_at'], name='mcp_token_actor_idx'),
        ]

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now() and self.client.is_active


class MCPAuditLog(models.Model):
    class Status(models.TextChoices):
        STARTED = 'started', 'Started'
        SUCCEEDED = 'succeeded', 'Succeeded'
        DENIED = 'denied', 'Denied'
        FAILED = 'failed', 'Failed'

    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    tool_name = models.CharField(max_length=120, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mcp_audit_logs',
    )
    client_id = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STARTED, db_index=True)
    arguments = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', '-started_at'], name='mcp_audit_user_time_idx'),
            models.Index(fields=['tool_name', 'status', '-started_at'], name='mcp_audit_tool_time_idx'),
        ]

    def __str__(self):
        return f'{self.tool_name} — {self.status}'
