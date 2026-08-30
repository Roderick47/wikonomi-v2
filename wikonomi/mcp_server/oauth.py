import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizeError,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .crypto import decrypt_secret, encrypt_secret, hash_secret
from .models import (
    MCPOAuthAuthorizationCode,
    MCPOAuthAuthorizationRequest,
    MCPOAuthClient,
    MCPOAuthToken,
)
from .permissions import READ_SCOPE, allowed_scopes_for_user, resolve_user_role


def public_base_url():
    return settings.WIKONOMI_MCP_PUBLIC_BASE_URL.rstrip('/')


def resource_url():
    return f'{public_base_url()}/mcp'


def _client_to_info(client):
    data = dict(client.metadata)
    data['client_id'] = client.client_id
    data['client_secret'] = decrypt_secret(client.encrypted_client_secret)
    return OAuthClientInformationFull.model_validate(data)


def _issue_token_pair(*, client, user, scopes, resource, family_id=None):
    now = timezone.now()
    access_raw = f'wka_{secrets.token_urlsafe(48)}'
    refresh_raw = f'wkr_{secrets.token_urlsafe(64)}'
    family_id = family_id or uuid.uuid4()

    MCPOAuthToken.objects.create(
        token_hash=hash_secret(access_raw),
        token_type=MCPOAuthToken.Type.ACCESS,
        client=client,
        user=user,
        scopes=scopes,
        resource=resource or resource_url(),
        family_id=family_id,
        expires_at=now + timedelta(seconds=settings.WIKONOMI_MCP_ACCESS_TOKEN_SECONDS),
    )
    MCPOAuthToken.objects.create(
        token_hash=hash_secret(refresh_raw),
        token_type=MCPOAuthToken.Type.REFRESH,
        client=client,
        user=user,
        scopes=scopes,
        resource=resource or resource_url(),
        family_id=family_id,
        expires_at=now + timedelta(seconds=settings.WIKONOMI_MCP_REFRESH_TOKEN_SECONDS),
    )
    return OAuthToken(
        access_token=access_raw,
        refresh_token=refresh_raw,
        token_type='Bearer',
        expires_in=settings.WIKONOMI_MCP_ACCESS_TOKEN_SECONDS,
        scope=' '.join(scopes),
    )


class DjangoOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """OAuth 2.1 provider backed by Wikonomi users and database records."""

    async def get_client(self, client_id):
        def load():
            client = MCPOAuthClient.objects.filter(client_id=client_id, is_active=True).first()
            return _client_to_info(client) if client else None

        return await sync_to_async(load, thread_sensitive=True)()

    async def register_client(self, client_info):
        def register():
            if (
                not MCPOAuthClient.objects.filter(client_id=client_info.client_id).exists()
                and MCPOAuthClient.objects.filter(is_active=True).count()
                >= settings.WIKONOMI_MCP_MAX_DYNAMIC_CLIENTS
            ):
                raise RegistrationError(
                    error='invalid_client_metadata',
                    error_description='This Wikonomi MCP has reached its dynamic-client limit.',
                )

            data = client_info.model_dump(mode='json')
            secret = data.pop('client_secret', None)
            try:
                MCPOAuthClient.objects.update_or_create(
                    client_id=client_info.client_id,
                    defaults={
                        'client_name': client_info.client_name or '',
                        'metadata': data,
                        'encrypted_client_secret': encrypt_secret(secret),
                        'is_active': True,
                    },
                )
            except IntegrityError as exc:
                raise RegistrationError(
                    error='invalid_client_metadata',
                    error_description='The OAuth client could not be registered.',
                ) from exc

        await sync_to_async(register, thread_sensitive=True)()

    async def authorize(self, client, params: AuthorizationParams):
        if params.resource and params.resource.rstrip('/') != resource_url().rstrip('/'):
            raise AuthorizeError(
                error='invalid_target',
                error_description='The requested resource is not Wikonomi MCP.',
            )

        def create_request():
            db_client = MCPOAuthClient.objects.get(client_id=client.client_id, is_active=True)
            pending = MCPOAuthAuthorizationRequest.objects.create(
                client=db_client,
                redirect_uri=str(params.redirect_uri),
                redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                state=params.state or '',
                scopes=params.scopes or [READ_SCOPE],
                code_challenge=params.code_challenge,
                resource=params.resource or resource_url(),
                expires_at=timezone.now() + timedelta(seconds=settings.WIKONOMI_MCP_AUTH_CODE_SECONDS),
            )
            query = urlencode({'request': str(pending.pk)})
            return f'{public_base_url()}/mcp/oauth/consent/?{query}'

        return await sync_to_async(create_request, thread_sensitive=True)()

    async def load_authorization_code(self, client, authorization_code):
        def load():
            code = MCPOAuthAuthorizationCode.objects.select_related('client', 'user').filter(
                code_hash=hash_secret(authorization_code),
                client__client_id=client.client_id,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).first()
            if not code or resolve_user_role(code.user) is None:
                return None
            return AuthorizationCode(
                code=authorization_code,
                client_id=code.client.client_id,
                scopes=list(code.scopes),
                expires_at=code.expires_at.timestamp(),
                code_challenge=code.code_challenge,
                redirect_uri=code.redirect_uri,
                redirect_uri_provided_explicitly=code.redirect_uri_provided_explicitly,
                resource=code.resource or resource_url(),
                subject=str(code.user_id),
            )

        return await sync_to_async(load, thread_sensitive=True)()

    async def exchange_authorization_code(self, client, authorization_code):
        def exchange():
            with transaction.atomic():
                code = MCPOAuthAuthorizationCode.objects.select_for_update().select_related(
                    'client', 'user'
                ).filter(
                    code_hash=hash_secret(authorization_code.code),
                    client__client_id=client.client_id,
                    used_at__isnull=True,
                    expires_at__gt=timezone.now(),
                ).first()
                if not code:
                    raise TokenError(error='invalid_grant', error_description='Authorization code is invalid or expired.')

                permitted = set(allowed_scopes_for_user(code.user))
                scopes = [scope for scope in code.scopes if scope in permitted]
                if READ_SCOPE not in scopes:
                    raise TokenError(error='invalid_scope', error_description='The Wikonomi account has no permitted MCP scopes.')

                code.used_at = timezone.now()
                code.save(update_fields=['used_at'])
                return _issue_token_pair(
                    client=code.client,
                    user=code.user,
                    scopes=scopes,
                    resource=code.resource or resource_url(),
                )

        return await sync_to_async(exchange, thread_sensitive=True)()

    async def load_refresh_token(self, client, refresh_token):
        def load():
            token = MCPOAuthToken.objects.select_related('client', 'user').filter(
                token_hash=hash_secret(refresh_token),
                token_type=MCPOAuthToken.Type.REFRESH,
                client__client_id=client.client_id,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).first()
            if not token or resolve_user_role(token.user) is None:
                return None
            return RefreshToken(
                token=refresh_token,
                client_id=token.client.client_id,
                scopes=list(token.scopes),
                expires_at=int(token.expires_at.timestamp()),
                subject=str(token.user_id),
            )

        return await sync_to_async(load, thread_sensitive=True)()

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        def exchange():
            with transaction.atomic():
                stored = MCPOAuthToken.objects.select_for_update().select_related('client', 'user').filter(
                    token_hash=hash_secret(refresh_token.token),
                    token_type=MCPOAuthToken.Type.REFRESH,
                    client__client_id=client.client_id,
                    revoked_at__isnull=True,
                    expires_at__gt=timezone.now(),
                ).first()
                if not stored:
                    raise TokenError(error='invalid_grant', error_description='Refresh token is invalid or expired.')

                permitted = set(allowed_scopes_for_user(stored.user))
                requested = scopes or list(stored.scopes)
                granted = [scope for scope in requested if scope in stored.scopes and scope in permitted]
                if READ_SCOPE not in granted:
                    raise TokenError(error='invalid_scope', error_description='The requested scopes are not permitted.')

                stored.revoked_at = timezone.now()
                stored.save(update_fields=['revoked_at'])
                return _issue_token_pair(
                    client=stored.client,
                    user=stored.user,
                    scopes=granted,
                    resource=stored.resource or resource_url(),
                    family_id=stored.family_id,
                )

        return await sync_to_async(exchange, thread_sensitive=True)()

    async def load_access_token(self, token):
        def load():
            stored = MCPOAuthToken.objects.select_related('client', 'user').filter(
                token_hash=hash_secret(token),
                token_type=MCPOAuthToken.Type.ACCESS,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
                client__is_active=True,
            ).first()
            if not stored or resolve_user_role(stored.user) is None:
                return None
            MCPOAuthClient.objects.filter(pk=stored.client_id).update(last_used_at=timezone.now())
            return AccessToken(
                token=token,
                client_id=stored.client.client_id,
                scopes=list(stored.scopes),
                expires_at=int(stored.expires_at.timestamp()),
                resource=stored.resource or resource_url(),
                subject=str(stored.user_id),
                claims={'iss': public_base_url()},
            )

        return await sync_to_async(load, thread_sensitive=True)()

    async def revoke_token(self, token):
        def revoke():
            stored = MCPOAuthToken.objects.filter(token_hash=hash_secret(token.token)).first()
            if not stored:
                return
            MCPOAuthToken.objects.filter(family_id=stored.family_id, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )

        await sync_to_async(revoke, thread_sensitive=True)()
