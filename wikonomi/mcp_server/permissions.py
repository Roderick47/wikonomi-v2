from dataclasses import dataclass

from django.contrib.auth import get_user_model

from .models import MCPUserAccess


READ_SCOPE = 'wikonomi:read'
WRITE_SCOPE = 'wikonomi:write'
PUBLISH_SCOPE = 'wikonomi:publish'
ALL_SCOPES = [READ_SCOPE, WRITE_SCOPE, PUBLISH_SCOPE]

ROLE_RANK = {
    MCPUserAccess.Role.READER: 10,
    MCPUserAccess.Role.CONTRIBUTOR: 20,
    MCPUserAccess.Role.TRUSTED: 20,
    MCPUserAccess.Role.STAFF: 30,
    MCPUserAccess.Role.OWNER: 40,
}

ROLE_SCOPES = {
    MCPUserAccess.Role.READER: [READ_SCOPE],
    MCPUserAccess.Role.CONTRIBUTOR: ALL_SCOPES,
    MCPUserAccess.Role.TRUSTED: ALL_SCOPES,
    MCPUserAccess.Role.STAFF: ALL_SCOPES,
    MCPUserAccess.Role.OWNER: ALL_SCOPES,
}


class MCPPermissionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class MCPActor:
    user: object
    role: str
    scopes: tuple[str, ...]
    client_id: str

    def has_scope(self, scope):
        return scope in self.scopes

    def at_least(self, role):
        return ROLE_RANK[self.role] >= ROLE_RANK[role]


def resolve_user_role(user):
    if not user or not user.is_authenticated or not user.is_active:
        return None
    try:
        access = user.mcp_access
    except MCPUserAccess.DoesNotExist:
        access = None

    # An explicit suspension must take precedence over default access, including
    # the superuser default. Tokens re-check this role on every use.
    if access is not None and not access.is_active:
        return None
    if user.is_superuser:
        return MCPUserAccess.Role.OWNER
    if access is not None:
        return access.role
    # Community contribution does not grant staff/admin privileges. An explicit
    # reader access record can still limit an account to search and retrieval.
    return MCPUserAccess.Role.CONTRIBUTOR


def allowed_scopes_for_user(user):
    role = resolve_user_role(user)
    return list(ROLE_SCOPES.get(role, []))


def get_user_for_subject(subject):
    if not subject:
        return None
    User = get_user_model()
    if str(subject).isdigit():
        return User.objects.filter(pk=int(subject), is_active=True).first()
    return User.objects.filter(username=subject, is_active=True).first()


def build_actor(*, user, token_scopes, client_id):
    role = resolve_user_role(user)
    if role is None:
        raise MCPPermissionDenied('This Wikonomi account does not have MCP access.')
    permitted = set(ROLE_SCOPES[role])
    effective_scopes = tuple(scope for scope in token_scopes if scope in permitted)
    return MCPActor(user=user, role=role, scopes=effective_scopes, client_id=client_id)


def require_actor(actor, *, scope=READ_SCOPE, minimum_role=MCPUserAccess.Role.READER):
    if not actor.has_scope(scope):
        raise MCPPermissionDenied(f'The connection is missing the required OAuth scope: {scope}.')
    if not actor.at_least(minimum_role):
        raise MCPPermissionDenied(f'This action requires the {minimum_role} role or higher.')
