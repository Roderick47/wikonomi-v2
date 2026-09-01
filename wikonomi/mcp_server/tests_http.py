"""End-to-end OAuth and MCP checks against the real ASGI app, without a network."""

import base64
import hashlib
import json
import re
from urllib.parse import parse_qs, urlparse

import httpx2
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from mcp.types import LATEST_PROTOCOL_VERSION

from guides.models import Guide
from wikonomi.asgi import application

from .models import MCPAuditLog
from .permissions import ALL_SCOPES
from .server import mcp_asgi_application


@override_settings(WIKONOMI_MCP_PUBLIC_BASE_URL='https://www.wikonomi.com')
class MCPASGIIntegrationTests(TransactionTestCase):
    def test_normal_login_oauth_pkce_guide_tools_refresh_and_revocation(self):
        user = get_user_model().objects.create_user(username='http-contributor', password='test-pass')
        self.assertTrue(self.client.login(username='http-contributor', password='test-pass'))
        session_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        guide_id = async_to_sync(self._run_flow)(session_cookie)
        guide = Guide.objects.get(pk=guide_id)
        self.assertEqual(guide.created_by, user)
        self.assertEqual(guide.current_version.edited_by, user)
        self.assertEqual(guide.current_version.status, 'published')
        self.assertEqual(guide.summary, 'Checked through authenticated ASGI tools.')
        self.assertEqual(guide.versions.count(), 2)
        self.assertTrue(guide.current_version.ai_assisted)
        self.assertEqual(MCPAuditLog.objects.count(), 2)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    async def _run_flow(self, session_cookie):
        base_url = 'https://www.wikonomi.com'
        callback = 'https://chatgpt.com/aip/callback'
        verifier = 'wikonomi-review-pkce-verifier-with-at-least-43-characters'
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        async with mcp_asgi_application.router.lifespan_context(mcp_asgi_application):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=application),
                base_url=base_url,
                cookies={settings.SESSION_COOKIE_NAME: session_cookie},
                follow_redirects=False,
                trust_env=False,
            ) as client:
                discovery = await client.get('/.well-known/oauth-authorization-server')
                self.assertEqual(discovery.status_code, 200)
                self.assertEqual(discovery.json()['issuer'], base_url)
                protected = await client.get('/.well-known/oauth-protected-resource/mcp')
                self.assertEqual(protected.status_code, 200)
                self.assertEqual(protected.json()['resource'], f'{base_url}/mcp')
                unauthorized = await client.get('/mcp')
                self.assertEqual(unauthorized.status_code, 401)
                self.assertIn('resource_metadata', unauthorized.headers['www-authenticate'])

                registered = await client.post('/register', json={
                    'client_name': 'Isolated ASGI review test',
                    'redirect_uris': [callback],
                    'grant_types': ['authorization_code', 'refresh_token'],
                    'response_types': ['code'],
                    'token_endpoint_auth_method': 'none',
                    'scope': ' '.join(ALL_SCOPES),
                })
                self.assertEqual(registered.status_code, 201)
                client_id = registered.json()['client_id']
                authorization = await client.get('/authorize', params={
                    'client_id': client_id,
                    'redirect_uri': callback,
                    'response_type': 'code',
                    'scope': ' '.join(ALL_SCOPES),
                    'state': 'isolated-review-state',
                    'code_challenge': challenge,
                    'code_challenge_method': 'S256',
                    'resource': f'{base_url}/mcp',
                })
                self.assertIn(authorization.status_code, (302, 303))
                consent_url = authorization.headers['location']
                pending_id = parse_qs(urlparse(consent_url).query)['request'][0]
                consent = await client.get(consent_url)
                self.assertEqual(consent.status_code, 200)
                self.assertIn('Create and update publicly visible guides', consent.text)
                csrf_token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', consent.text).group(1)
                approved = await client.post(consent_url, data={
                    'request': pending_id,
                    'action': 'approve',
                    'csrfmiddlewaretoken': csrf_token,
                }, headers={'Referer': consent_url})
                self.assertEqual(approved.status_code, 302)
                callback_query = parse_qs(urlparse(approved.headers['location']).query)
                self.assertEqual(callback_query['state'], ['isolated-review-state'])
                token_response = await client.post('/token', data={
                    'grant_type': 'authorization_code',
                    'client_id': client_id,
                    'code': callback_query['code'][0],
                    'code_verifier': verifier,
                    'redirect_uri': callback,
                    'resource': f'{base_url}/mcp',
                })
                self.assertEqual(token_response.status_code, 200)
                tokens = token_response.json()
                self.assertEqual(set(tokens['scope'].split()), set(ALL_SCOPES))
                headers = {
                    'Authorization': f"Bearer {tokens['access_token']}",
                    'Accept': 'application/json, text/event-stream',
                }

                async def rpc(request_id, method, params):
                    response = await client.post('/mcp', headers=headers, json={
                        'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params,
                    })
                    self.assertEqual(response.status_code, 200)
                    if response.headers['content-type'].startswith('text/event-stream'):
                        messages = [json.loads(line[6:]) for line in response.text.splitlines()
                                    if line.startswith('data: ')]
                        payload = next(message for message in messages if message.get('id') == request_id)
                    else:
                        payload = response.json()
                    self.assertNotIn('error', payload)
                    self.assertFalse(payload['result'].get('isError', False))
                    return payload['result']

                initialized = await rpc(1, 'initialize', {
                    'protocolVersion': LATEST_PROTOCOL_VERSION,
                    'capabilities': {},
                    'clientInfo': {'name': 'isolated-review-test', 'version': '1.0'},
                })
                headers['MCP-Protocol-Version'] = initialized['protocolVersion']
                listed = await rpc(2, 'tools/list', {})
                self.assertIn('create_guide', {tool['name'] for tool in listed['tools']})
                created = await rpc(3, 'tools/call', {
                    'name': 'create_guide',
                    'arguments': {'guide': {
                        'title': 'Isolated HTTP review guide',
                        'steps': [{'instruction': 'Compare observed dates.'}],
                    }},
                })
                guide_id = created['structuredContent']['id']
                read = await rpc(4, 'tools/call', {'name': 'get_guide', 'arguments': {'guide_id': guide_id}})
                self.assertNotIn('ai_assisted', read['structuredContent'])
                await rpc(5, 'tools/call', {
                    'name': 'update_guide',
                    'arguments': {'guide_id': guide_id, 'changes': {
                        'summary': 'Checked through authenticated ASGI tools.',
                    }},
                })

                refreshed = await client.post('/token', data={
                    'grant_type': 'refresh_token', 'client_id': client_id,
                    'refresh_token': tokens['refresh_token'],
                })
                self.assertEqual(refreshed.status_code, 200)
                refreshed_tokens = refreshed.json()
                self.assertNotEqual(refreshed_tokens['refresh_token'], tokens['refresh_token'])
                # A different registered client must not be able to revoke
                # this user's token family, even if it knows the token.
                other_client = await client.post('/register', json={
                    'client_name': 'Other isolated test client',
                    'redirect_uris': [callback],
                    'grant_types': ['authorization_code', 'refresh_token'],
                    'token_endpoint_auth_method': 'none',
                })
                self.assertEqual(other_client.status_code, 201)
                unrelated = await client.post('/revoke', data={
                    'client_id': other_client.json()['client_id'],
                    'token': refreshed_tokens['access_token'],
                })
                self.assertEqual(unrelated.status_code, 200)
                headers['Authorization'] = f"Bearer {refreshed_tokens['access_token']}"
                await rpc(6, 'tools/call', {'name': 'get_guide', 'arguments': {'guide_id': guide_id}})
                missing_token = await client.post('/revoke', data={'client_id': client_id})
                self.assertEqual(missing_token.status_code, 400)
                revoked = await client.post('/revoke', data={
                    'client_id': client_id, 'token': refreshed_tokens['access_token'],
                    'token_type_hint': 'access_token',
                })
                self.assertEqual(revoked.status_code, 200)
                denied = await client.get('/mcp', headers={
                    'Authorization': f"Bearer {refreshed_tokens['access_token']}",
                })
                self.assertEqual(denied.status_code, 401)
                replay = await client.post('/token', data={
                    'grant_type': 'refresh_token', 'client_id': client_id,
                    'refresh_token': refreshed_tokens['refresh_token'],
                })
                self.assertEqual(replay.status_code, 400)
                for method in ('client_secret_post', 'client_secret_basic'):
                    registered_secret_client = await client.post('/register', json={
                        'client_name': f'Isolated {method} test',
                        'redirect_uris': [callback],
                        'grant_types': ['authorization_code', 'refresh_token'],
                        'token_endpoint_auth_method': method,
                    })
                    self.assertEqual(registered_secret_client.status_code, 201)
                    secret_client = registered_secret_client.json()
                    revocation_data = {'client_id': secret_client['client_id'], 'token': 'unknown-test-token'}
                    missing_secret = await client.post('/revoke', data=revocation_data)
                    self.assertEqual(missing_secret.status_code, 401)
                    if method == 'client_secret_basic':
                        valid = await client.post('/revoke', data=revocation_data, auth=httpx2.BasicAuth(
                            secret_client['client_id'], secret_client['client_secret'],
                        ))
                    else:
                        valid = await client.post('/revoke', data={
                            **revocation_data, 'client_secret': secret_client['client_secret'],
                        })
                    self.assertEqual(valid.status_code, 200)
                return guide_id
