import base64
import io
import tempfile
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import Business, PriceReport, Product
from guides.models import Guide, GuideVersion, Step

from .crypto import decrypt_secret, encrypt_secret, hash_secret
from .models import (
    MCPOAuthAuthorizationCode,
    MCPOAuthAuthorizationRequest,
    MCPOAuthClient,
    MCPOAuthToken,
    MCPUserAccess,
)
from .permissions import (
    ALL_SCOPES,
    MCPActor,
    MCPPermissionDenied,
    READ_SCOPE,
    WRITE_SCOPE,
    allowed_scopes_for_user,
    resolve_user_role,
)
from .oauth import DjangoOAuthProvider
from .server import mcp
from .services import create_guide, submit_price, update_guide, upload_evidence


class MCPPermissionTests(TestCase):
    def test_roles_are_deny_by_default_with_owner_only_superuser_default(self):
        User = get_user_model()
        ordinary = User.objects.create_user(username='ordinary')
        staff = User.objects.create_user(username='staff', is_staff=True)
        owner = User.objects.create_superuser(username='owner', email='owner@example.com', password='pass')

        self.assertIsNone(resolve_user_role(ordinary))
        self.assertIsNone(resolve_user_role(staff))
        self.assertEqual(resolve_user_role(owner), MCPUserAccess.Role.OWNER)
        self.assertEqual(allowed_scopes_for_user(owner), ALL_SCOPES)

        access = MCPUserAccess.objects.create(user=ordinary, role=MCPUserAccess.Role.TRUSTED)
        MCPUserAccess.objects.create(user=staff, role=MCPUserAccess.Role.STAFF)
        self.assertEqual(resolve_user_role(ordinary), MCPUserAccess.Role.TRUSTED)
        self.assertEqual(resolve_user_role(staff), MCPUserAccess.Role.STAFF)
        self.assertEqual(allowed_scopes_for_user(ordinary), [READ_SCOPE, WRITE_SCOPE])

        access.is_active = False
        access.save(update_fields=['is_active'])
        self.assertIsNone(resolve_user_role(ordinary))

    def test_client_secrets_are_encrypted_and_tokens_are_one_way_hashed(self):
        encrypted = encrypt_secret('client-secret')
        self.assertNotEqual(encrypted, 'client-secret')
        self.assertEqual(decrypt_secret(encrypted), 'client-secret')
        self.assertEqual(len(hash_secret('opaque-token')), 64)


@override_settings(WIKONOMI_MCP_PUBLIC_BASE_URL='https://www.wikonomi.com')
class MCPServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='mcp-owner')
        self.actor = MCPActor(
            user=self.user,
            role=MCPUserAccess.Role.OWNER,
            scopes=tuple(ALL_SCOPES),
            client_id='test-client',
        )
        self.business = Business.objects.create(name='Test Market', slug='test-market')
        self.product = Product.objects.create(name='Rice 1kg', slug='rice-1kg', created_by=self.user)

    def test_price_write_is_published_with_provenance_and_idempotency(self):
        payload = {
            'product_id': self.product.pk,
            'business_id': self.business.pk,
            'price': Decimal('8.50'),
            'currency': 'PGK',
            'notes': 'Shelf label checked',
            'idempotency_key': 'photo-123-row-1',
        }
        ai = {
            'provider': 'OpenAI',
            'model': 'gpt-test',
            'confidence': 0.94,
            'source_note': 'Extracted from a user-provided shelf photo.',
        }

        first = submit_price(actor=self.actor, data=payload, ai=ai)
        second = submit_price(actor=self.actor, data=payload, ai=ai)
        report = PriceReport.objects.get(pk=first['price_report_id'])

        self.assertEqual(first['status'], 'created')
        self.assertEqual(second['status'], 'already_exists')
        self.assertEqual(PriceReport.objects.count(), 1)
        self.assertEqual(report.created_via, 'mcp')
        self.assertTrue(report.ai_assisted)
        self.assertEqual(report.ai_provider, 'OpenAI')
        self.assertEqual(report.ai_confidence, Decimal('0.940'))
        self.assertEqual(report.user, self.user)

    def test_evidence_is_validated_deduplicated_and_linked(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            report = PriceReport.objects.create(
                product=self.product,
                business=self.business,
                user=self.user,
                price=Decimal('5.00'),
            )
            buffer = io.BytesIO()
            Image.new('RGB', (16, 16), color='green').save(buffer, format='PNG')
            encoded = base64.b64encode(buffer.getvalue()).decode('ascii')

            first = upload_evidence(
                actor=self.actor,
                price_report_ids=[report.pk],
                image_base64=encoded,
                filename='shelf.png',
                caption='Shelf price',
            )
            second = upload_evidence(
                actor=self.actor,
                price_report_ids=[report.pk],
                image_base64=encoded,
                filename='shelf.png',
                caption='Shelf price',
            )

        photo = report.photos.get()
        self.assertEqual(len(first['attached']), 1)
        self.assertEqual(second['skipped'][0]['reason'], 'duplicate_evidence')
        self.assertEqual(photo.created_via, 'mcp')
        self.assertEqual(photo.uploaded_by, self.user)

    def test_guides_publish_immediately_with_sources_and_protect_other_authors(self):
        created = create_guide(
            actor=self.actor,
            data={
                'title': 'How to compare rice prices',
                'summary': 'A small test guide.',
                'steps': [{'title': 'Search', 'instruction': 'Search for the exact pack size.'}],
                'references': [{
                    'title': 'Wikonomi',
                    'url': 'https://www.wikonomi.com/',
                    'publisher': 'Wikonomi',
                    'accessed_at': timezone.localdate().isoformat(),
                }],
                'idempotency_key': 'guide-123',
            },
            ai={'provider': 'OpenAI', 'confidence': 0.8},
        )
        guide = Guide.objects.get(pk=created['id'])

        self.assertEqual(created['status'], 'created_and_published')
        self.assertEqual(guide.current_version.status, 'published')
        self.assertTrue(guide.current_version.ai_assisted)
        self.assertEqual(guide.current_version.references.count(), 1)
        self.assertEqual(guide.current_version.steps.count(), 1)

        other = get_user_model().objects.create_user(username='guide-author')
        protected = Guide.objects.create(title='Protected guide', slug='protected-guide', created_by=other)
        version = GuideVersion.objects.create(guide=protected, edited_by=other)
        Step.objects.create(version=version, position=1, instruction='Original')
        protected.current_version = version
        protected.save(update_fields=['current_version'])

        with self.assertRaises(MCPPermissionDenied):
            update_guide(
                actor=self.actor,
                guide_id=protected.pk,
                changes={'summary': 'Changed'},
                confirm_high_impact=False,
            )


class MCPOAuthConsentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='trusted-user', password='pass')
        MCPUserAccess.objects.create(user=self.user, role=MCPUserAccess.Role.TRUSTED)
        self.oauth_client = MCPOAuthClient.objects.create(
            client_id='chatgpt-test',
            client_name='ChatGPT test',
            metadata={},
        )
        self.pending = MCPOAuthAuthorizationRequest.objects.create(
            client=self.oauth_client,
            redirect_uri='https://chatgpt.com/aip/callback',
            state='state-123',
            scopes=ALL_SCOPES,
            code_challenge='challenge',
            resource='https://www.wikonomi.com/mcp',
            expires_at=timezone.now() + timedelta(minutes=5),
        )

    def test_consent_grants_only_scopes_allowed_by_the_wikonomi_role(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('mcp_server:oauth_consent'), {
            'request': self.pending.pk,
            'action': 'approve',
        })

        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response['Location']).query)
        raw_code = query['code'][0]
        code = MCPOAuthAuthorizationCode.objects.get(code_hash=hash_secret(raw_code))
        self.assertEqual(query['state'], ['state-123'])
        self.assertEqual(code.user, self.user)
        self.assertEqual(code.scopes, [READ_SCOPE, WRITE_SCOPE])
        self.assertNotIn('wikonomi:publish', code.scopes)

    def test_authorization_code_exchange_refresh_rotation_and_revocation(self):
        self.oauth_client.metadata = {
            'client_name': 'ChatGPT test',
            'redirect_uris': ['https://chatgpt.com/aip/callback'],
            'grant_types': ['authorization_code', 'refresh_token'],
            'response_types': ['code'],
            'token_endpoint_auth_method': 'none',
            'scope': ' '.join(ALL_SCOPES),
        }
        self.oauth_client.save(update_fields=['metadata'])
        raw_code = 'wkc_test-authorization-code'
        MCPOAuthAuthorizationCode.objects.create(
            code_hash=hash_secret(raw_code),
            client=self.oauth_client,
            user=self.user,
            scopes=[READ_SCOPE, WRITE_SCOPE],
            code_challenge='challenge',
            redirect_uri='https://chatgpt.com/aip/callback',
            resource='https://www.wikonomi.com/mcp',
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        provider = DjangoOAuthProvider()
        client_info = async_to_sync(provider.get_client)(self.oauth_client.client_id)
        authorization_code = async_to_sync(provider.load_authorization_code)(client_info, raw_code)
        issued = async_to_sync(provider.exchange_authorization_code)(client_info, authorization_code)
        access = async_to_sync(provider.load_access_token)(issued.access_token)
        refresh = async_to_sync(provider.load_refresh_token)(client_info, issued.refresh_token)

        self.assertEqual(access.subject, str(self.user.pk))
        self.assertEqual(access.scopes, [READ_SCOPE, WRITE_SCOPE])
        self.assertEqual(refresh.subject, str(self.user.pk))
        self.assertFalse(MCPOAuthToken.objects.filter(token_hash=issued.access_token).exists())
        self.assertTrue(MCPOAuthToken.objects.filter(token_hash=hash_secret(issued.access_token)).exists())

        rotated = async_to_sync(provider.exchange_refresh_token)(client_info, refresh, [READ_SCOPE])
        self.assertIsNone(async_to_sync(provider.load_refresh_token)(client_info, issued.refresh_token))
        rotated_access = async_to_sync(provider.load_access_token)(rotated.access_token)
        self.assertEqual(rotated_access.scopes, [READ_SCOPE])

        async_to_sync(provider.revoke_token)(rotated_access)
        self.assertIsNone(async_to_sync(provider.load_access_token)(rotated.access_token))


class MCPToolSchemaTests(TestCase):
    def test_expected_safe_tool_surface_is_registered(self):
        tools = async_to_sync(mcp.list_tools)()
        names = {tool.name for tool in tools}

        self.assertEqual(names, {
            'get_schema_help',
            'search_wikonomi',
            'get_product',
            'find_or_create_product',
            'submit_price',
            'bulk_submit_prices',
            'upload_evidence',
            'get_guide',
            'create_guide',
            'update_guide',
        })
        self.assertNotIn('delete_product', names)
        self.assertNotIn('merge_product', names)
