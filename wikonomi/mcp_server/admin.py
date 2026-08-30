from django.contrib import admin

from .models import (
    MCPAuditLog,
    MCPOAuthAuthorizationCode,
    MCPOAuthAuthorizationRequest,
    MCPOAuthClient,
    MCPOAuthToken,
    MCPUserAccess,
)


@admin.register(MCPUserAccess)
class MCPUserAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_active', 'updated_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'user__email')


@admin.register(MCPOAuthClient)
class MCPOAuthClientAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'client_id', 'is_active', 'created_at', 'last_used_at')
    list_filter = ('is_active',)
    search_fields = ('client_name', 'client_id')
    readonly_fields = ('client_id', 'metadata', 'encrypted_client_secret', 'created_at', 'updated_at', 'last_used_at')


@admin.register(MCPAuditLog)
class MCPAuditLogAdmin(admin.ModelAdmin):
    list_display = ('tool_name', 'user', 'role', 'status', 'started_at', 'completed_at')
    list_filter = ('status', 'role', 'tool_name')
    search_fields = ('user__username', 'client_id', 'correlation_id')
    readonly_fields = [field.name for field in MCPAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


for model in (MCPOAuthAuthorizationRequest, MCPOAuthAuthorizationCode, MCPOAuthToken):
    admin.site.register(model)
