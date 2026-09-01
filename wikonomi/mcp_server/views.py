import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from mcp.server.auth.provider import construct_redirect_uri

from .crypto import hash_secret
from .models import MCPOAuthAuthorizationCode, MCPOAuthAuthorizationRequest
from .oauth import resource_url
from .permissions import READ_SCOPE, allowed_scopes_for_user, resolve_user_role


@require_http_methods(['GET', 'HEAD'])
def openai_apps_challenge(request):
    """Publish only the domain-verification token supplied by the owner."""
    token = settings.WIKONOMI_OPENAI_APPS_CHALLENGE
    if not token or any(char.isspace() for char in token):
        return HttpResponseNotFound('No plugin verification challenge is configured.')
    response = HttpResponse(token, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_http_methods(['GET', 'POST'])
def oauth_consent(request):
    pending_id = request.GET.get('request') or request.POST.get('request')
    try:
        parsed_pending_id = uuid.UUID(str(pending_id))
    except (TypeError, ValueError, AttributeError):
        return HttpResponseNotFound('This MCP authorization request does not exist.')

    pending = MCPOAuthAuthorizationRequest.objects.select_related('client').filter(pk=parsed_pending_id).first()
    if not pending:
        return HttpResponseNotFound('This MCP authorization request does not exist.')
    if pending.completed_at or pending.is_expired:
        return HttpResponseForbidden('This MCP authorization request has expired or was already used.')

    role = resolve_user_role(request.user)
    if role is None:
        return HttpResponseForbidden('Your Wikonomi account has not been granted MCP access.')

    permitted_scopes = set(allowed_scopes_for_user(request.user))
    requested_scopes = [scope for scope in pending.scopes if scope in permitted_scopes]
    if READ_SCOPE not in requested_scopes:
        return HttpResponseForbidden('Your Wikonomi MCP role does not allow the requested access.')

    if request.method == 'POST':
        action = request.POST.get('action')
        with transaction.atomic():
            pending = MCPOAuthAuthorizationRequest.objects.select_for_update().select_related('client').get(
                pk=parsed_pending_id
            )
            if pending.completed_at or pending.is_expired:
                return HttpResponseForbidden('This MCP authorization request has expired or was already used.')
            pending.completed_at = timezone.now()
            pending.save(update_fields=['completed_at'])

            if action != 'approve':
                return redirect(construct_redirect_uri(
                    pending.redirect_uri,
                    error='access_denied',
                    state=pending.state or None,
                ))

            raw_code = f'wkc_{secrets.token_urlsafe(40)}'
            MCPOAuthAuthorizationCode.objects.create(
                code_hash=hash_secret(raw_code),
                client=pending.client,
                user=request.user,
                scopes=requested_scopes,
                code_challenge=pending.code_challenge,
                redirect_uri=pending.redirect_uri,
                redirect_uri_provided_explicitly=pending.redirect_uri_provided_explicitly,
                resource=pending.resource or resource_url(),
                expires_at=timezone.now() + timedelta(seconds=settings.WIKONOMI_MCP_AUTH_CODE_SECONDS),
            )
        return redirect(construct_redirect_uri(
            pending.redirect_uri,
            code=raw_code,
            state=pending.state or None,
        ))

    return render(request, 'mcp_server/oauth_consent.html', {
        'pending': pending,
        'requested_scopes': requested_scopes,
        'role': role,
    })
