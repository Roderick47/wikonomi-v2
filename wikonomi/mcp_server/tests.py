import base64
import io
import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pydantic import ValidationError
from mcp.server.mcpserver.exceptions import ToolError

from core.models import Business, PriceReport, Product
from guides.models import Guide, GuideVersion, Step

from .crypto import decrypt_secret, encrypt_secret, hash_secret
from .models import (
    MCPAuditLog,
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
    PUBLISH_SCOPE,
    READ_SCOPE,
    WRITE_SCOPE,
    allowed_scopes_for_user,
    build_actor,
    require_actor,
    resolve_user_role,
)
from .oauth import DjangoOAuthProvider
from .server import mcp
from .services import (
    audited_call,
    create_guide,
    get_guide,
    get_product,
    search_wikonomi,
    submit_price,
    update_guide,
    upload_evidence,
)
from .tools import PriceObservation


class MCPPermissionTests(TestCase):
    def test_active_accounts_can_contribute_without_gaining_staff_access(self):
        User = get_user_model()
        ordinary = User.objects.create_user(username='ordinary')
        staff = User.objects.create_user(username='staff', is_staff=True)
        owner = User.objects.create_superuser(username='owner', email='owner@example.com', password='pass')

        self.assertEqual(resolve_user_role(ordinary), MCPUserAccess.Role.CONTRIBUTOR)
        self.assertEqual(resolve_user_role(staff), MCPUserAccess.Role.CONTRIBUTOR)
        self.assertEqual(allowed_scopes_for_user(ordinary), ALL_SCOPES)
        self.assertEqual(allowed_scopes_for_user(staff), ALL_SCOPES)
        actor = build_actor(user=ordinary, token_scopes=ALL_SCOPES, client_id='test-client')
        self.assertFalse(actor.at_least(MCPUserAccess.Role.STAFF))
        self.assertFalse(ordinary.is_staff)
        self.assertFalse(ordinary.is_superuser)
        self.assertEqual(resolve_user_role(owner), MCPUserAccess.Role.OWNER)
        self.assertEqual(allowed_scopes_for_user(owner), ALL_SCOPES)

        access = MCPUserAccess.objects.create(user=ordinary, role=MCPUserAccess.Role.TRUSTED)
        MCPUserAccess.objects.create(user=staff, role=MCPUserAccess.Role.STAFF)
        self.assertEqual(resolve_user_role(ordinary), MCPUserAccess.Role.TRUSTED)
        self.assertEqual(resolve_user_role(staff), MCPUserAccess.Role.STAFF)
        self.assertEqual(allowed_scopes_for_user(ordinary), ALL_SCOPES)

        access.is_active = False
        access.save(update_fields=['is_active'])
        self.assertIsNone(resolve_user_role(ordinary))

    def test_anonymous_and_inactive_accounts_have_no_access(self):
        inactive = get_user_model().objects.create_user(username='inactive', is_active=False)
        for user in (None, AnonymousUser(), inactive):
            with self.subTest(user=user):
                self.assertIsNone(resolve_user_role(user))
                self.assertEqual(allowed_scopes_for_user(user), [])

    def test_explicit_suspension_overrides_superuser_default(self):
        owner = get_user_model().objects.create_user(username='suspended-owner', is_superuser=True)
        MCPUserAccess.objects.create(user=owner, role=MCPUserAccess.Role.OWNER, is_active=False)
        self.assertIsNone(resolve_user_role(owner))
        with self.assertRaises(MCPPermissionDenied):
            build_actor(user=owner, token_scopes=ALL_SCOPES, client_id='test-client')

    def test_reader_cannot_gain_write_access_from_claimed_token_scopes(self):
        user = get_user_model().objects.create_user(username='reader')
        MCPUserAccess.objects.create(user=user, role=MCPUserAccess.Role.READER)
        actor = build_actor(user=user, token_scopes=ALL_SCOPES, client_id='test-client')
        self.assertEqual(actor.scopes, (READ_SCOPE,))
        require_actor(actor)
        for scope in (WRITE_SCOPE, PUBLISH_SCOPE):
            with self.subTest(scope=scope), self.assertRaises(MCPPermissionDenied):
                require_actor(actor, scope=scope)

    def test_read_token_does_not_gain_scopes_after_role_upgrade(self):
        user = get_user_model().objects.create_user(username='upgraded-reader')
        MCPUserAccess.objects.create(user=user, role=MCPUserAccess.Role.TRUSTED)
        actor = build_actor(user=user, token_scopes=[READ_SCOPE], client_id='test-client')
        self.assertEqual(actor.role, MCPUserAccess.Role.TRUSTED)
        with self.assertRaises(MCPPermissionDenied):
            require_actor(actor, scope=WRITE_SCOPE, minimum_role=MCPUserAccess.Role.TRUSTED)

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
        self.assertEqual(report.ai_model, 'gpt-test')
        self.assertEqual(report.ai_confidence, Decimal('0.940'))
        self.assertEqual(report.ai_source_note, ai['source_note'])
        self.assertEqual(report.user, self.user)

    def test_public_price_pages_and_tool_results_hide_internal_provenance(self):
        result = submit_price(
            actor=self.actor,
            data={'product_id': self.product.pk, 'business_id': self.business.pk, 'price': Decimal('8.50')},
            ai={'provider': 'internal-provider-marker', 'model': 'internal-model-marker',
                'source_note': 'private-provenance-marker', 'confidence': 0.83},
        )
        self.product.ai_assisted = True
        self.product.save(update_fields=['ai_assisted'])
        for route, pk in (
            ('price_detail', result['price_report_id']),
            ('product_detail', self.product.pk),
            ('business_detail', self.business.pk),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=[pk]))
                self.assertContains(response, 'Rice 1kg')
                for private_text in ('Added with AI', 'AI-assisted', 'internal-provider-marker',
                                     'internal-model-marker', 'private-provenance-marker'):
                    self.assertNotContains(response, private_text)
        product = get_product(self.product.pk)
        self.assertNotIn('ai_assisted', product)
        self.assertNotIn('ai_assisted', product['recent_prices'][0])
        self.assertEqual(product['recent_prices'][0]['id'], result['price_report_id'])
        self.assertTrue(PriceReport.objects.get(pk=result['price_report_id']).ai_assisted)

    def test_read_only_calls_do_not_store_queries_but_write_attempts_are_audited(self):
        with patch('mcp_server.services.current_actor', return_value=self.actor):
            result = audited_call(
                'search_wikonomi', {'query': 'Rice'}, scope=READ_SCOPE,
                minimum_role=MCPUserAccess.Role.READER,
                operation=lambda actor: search_wikonomi('Rice'),
            )
            self.assertEqual(result['count'], 1)
            self.assertEqual(MCPAuditLog.objects.count(), 0)
            written = audited_call(
                'submit_price', {'image_base64': 'private-image-data'}, scope=WRITE_SCOPE,
                minimum_role=MCPUserAccess.Role.TRUSTED,
                operation=lambda actor: submit_price(
                    actor=actor, data={'product_id': self.product.pk,
                                      'business_id': self.business.pk, 'price': Decimal('8.50')},
                ),
            )
        log = MCPAuditLog.objects.get()
        self.assertEqual(log.status, MCPAuditLog.Status.SUCCEEDED)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.arguments['image_base64'], '[redacted]')
        self.assertEqual(log.response_summary['price_report_id'], written['price_report_id'])

    def test_reader_write_denial_is_audited_without_running_operation(self):
        MCPUserAccess.objects.create(user=self.user, role=MCPUserAccess.Role.READER)
        reader = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='reader-client')
        operation = Mock()
        with patch('mcp_server.services.current_actor', return_value=reader):
            with self.assertRaises(MCPPermissionDenied):
                audited_call('submit_price', {}, scope=WRITE_SCOPE,
                             minimum_role=MCPUserAccess.Role.TRUSTED, operation=operation)
        operation.assert_not_called()
        self.assertEqual(PriceReport.objects.count(), 0)
        self.assertEqual(MCPAuditLog.objects.get().status, MCPAuditLog.Status.DENIED)

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
        self.assertNotIn('ai_assisted', created)
        self.assertNotIn('ai_assisted', get_guide(guide.pk))
        searched = search_wikonomi('How to compare rice prices', ['guide'])['results'][0]
        self.assertNotIn('ai_assisted', searched)
        response = self.client.get(reverse('guides:detail', args=[guide.slug]))
        self.assertContains(response, 'Created by @mcp-owner')
        self.assertContains(response, 'id="guide-sources-title"')
        self.assertContains(response, 'https://www.wikonomi.com/')
        self.assertNotContains(response, 'AI-assisted')
        self.assertNotContains(response, 'via OpenAI')

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

    def test_guide_updates_keep_internal_provenance_without_public_metadata(self):
        created = create_guide(
            actor=self.actor,
            data={'title': 'Source test', 'steps': [{'instruction': 'Check the shelf.'}]},
            ai={'provider': 'first-provider'},
        )
        guide = Guide.objects.get(pk=created['id'])
        previous_version = guide.current_version
        updated = update_guide(
            actor=self.actor, guide_id=guide.pk,
            changes={'summary': 'Updated summary'}, confirm_high_impact=False,
            ai={'provider': 'internal-provider-marker', 'model': 'internal-model-marker',
                'source_note': 'private-provenance-marker', 'confidence': 0.83},
        )
        guide.refresh_from_db()
        previous_version.refresh_from_db()
        self.assertEqual(previous_version.ai_provider, 'first-provider')
        self.assertNotEqual(guide.current_version_id, previous_version.pk)
        self.assertEqual(guide.current_version.ai_provider, 'internal-provider-marker')
        self.assertEqual(guide.current_version.ai_model, 'internal-model-marker')
        self.assertEqual(guide.current_version.ai_source_note, 'private-provenance-marker')
        self.assertEqual(guide.current_version.ai_confidence, Decimal('0.830'))
        self.assertTrue(guide.ai_assisted)
        self.assertNotIn('ai_assisted', updated)
        response = self.client.get(reverse('guides:detail', args=[guide.slug]))
        self.assertContains(response, 'Updated summary')
        for private_text in ('AI-assisted', 'internal-provider-marker', 'internal-model-marker',
                             'private-provenance-marker', 'Confidence 0.83'):
            self.assertNotContains(response, private_text)

    def test_unpublished_guides_are_not_disclosed_by_read_tools(self):
        for status in ('pending', 'rejected', None):
            with self.subTest(status=status):
                guide = Guide.objects.create(title=f'Internal {status}', slug=f'internal-{status}')
                if status:
                    guide.current_version = GuideVersion.objects.create(guide=guide, status=status)
                    guide.save(update_fields=['current_version'])
                with self.assertRaisesRegex(ValueError, 'was not found'):
                    get_guide(guide.pk)
        self.assertEqual(search_wikonomi('Internal', ['guide'])['results'], [])

    def test_internal_report_counts_ai_prices_without_counting_retries_twice(self):
        payload = {'product_id': self.product.pk, 'business_id': self.business.pk,
                   'price': Decimal('8.50'), 'idempotency_key': 'count-once'}
        for _ in range(2):
            submit_price(actor=self.actor, data=payload, ai={'provider': 'OpenAI', 'model': 'test-model'})
        PriceReport.objects.create(product=self.product, business=self.business, user=self.user, price=9)
        create_guide(actor=self.actor, data={'title': 'Counted guide', 'steps': [{'instruction': 'Check.'}]})
        output = io.StringIO()
        call_command('mcp_provenance_stats', stdout=output)
        result = json.loads(output.getvalue())
        self.assertEqual(result['prices'], {'total': 2, 'ai_assisted': 1, 'mcp': 1})
        self.assertEqual(result['products'], {'total': 1, 'ai_assisted': 0, 'mcp': 0})
        self.assertEqual(result['guides'], {'total': 1, 'ai_assisted': 1, 'mcp': 1})
        self.assertEqual(result['guide_versions'], {'total': 1, 'ai_assisted': 1, 'mcp': 1})
        self.assertEqual(result['ai_price_breakdown'], [
            {'ai_provider': 'OpenAI', 'ai_model': 'test-model', 'count': 1},
        ])
        self.assertEqual(PriceReport.objects.count(), 2)


class MCPContributorToolTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='community-member')
        self.actor = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='contributor-client')

    def call_tool(self, name, arguments):
        with patch('mcp_server.services.current_actor', return_value=self.actor):
            result = async_to_sync(mcp.call_tool)(name, arguments)
        self.assertFalse(result.is_error)
        return result.structured_content

    def create_guide(self):
        return self.call_tool('create_guide', {
            'guide': {
                'title': 'Community price comparison guide',
                'steps': [{'instruction': 'Compare the same pack size.'}],
                'references': [{'title': 'Wikonomi', 'url': 'https://www.wikonomi.com/'}],
            },
        })

    def test_regular_member_can_create_and_edit_guide_through_registered_tools(self):
        created = self.create_guide()
        guide = Guide.objects.get(pk=created['id'])
        original_version = guide.current_version
        updated = self.call_tool('update_guide', {
            'guide_id': guide.pk,
            'changes': {'summary': 'Also compare the observation dates.'},
        })
        guide.refresh_from_db()
        self.assertEqual(updated['summary'], 'Also compare the observation dates.')
        self.assertEqual(guide.created_by, self.user)
        self.assertEqual(guide.current_version.edited_by, self.user)
        self.assertEqual(guide.current_version.status, 'published')
        self.assertEqual(guide.versions.count(), 2)
        self.assertTrue(GuideVersion.objects.filter(pk=original_version.pk).exists())
        self.assertEqual(guide.current_version.references.count(), 1)
        self.assertTrue(guide.current_version.ai_assisted)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def test_editing_another_authors_guide_requires_confirmation(self):
        created = self.create_guide()
        other = get_user_model().objects.create_user(username='second-community-member')
        self.actor = build_actor(user=other, token_scopes=ALL_SCOPES, client_id='second-client')
        arguments = {'guide_id': created['id'], 'changes': {'summary': 'Community correction.'}}
        with self.assertRaises(ToolError):
            self.call_tool('update_guide', arguments)
        guide = Guide.objects.get(pk=created['id'])
        self.assertEqual(guide.versions.count(), 1)
        self.call_tool('update_guide', {**arguments, 'confirm_high_impact': True})
        guide.refresh_from_db()
        self.assertEqual(guide.current_version.edited_by, other)
        self.assertEqual(guide.created_by, self.user)
        self.assertEqual(guide.versions.count(), 2)

    def test_contributor_cannot_overwrite_a_guide_marked_for_deletion(self):
        created = self.create_guide()
        guide = Guide.objects.get(pk=created['id'])
        guide.mark_for_deletion(self.user, reason='Needs moderation')
        with self.assertRaises(ToolError):
            self.call_tool('update_guide', {
                'guide_id': guide.pk, 'changes': {'summary': 'Cannot bypass moderation.'},
                'confirm_high_impact': True,
            })
        self.assertEqual(guide.versions.count(), 1)

    def test_contributor_cannot_turn_an_unpublished_guide_into_a_published_one(self):
        created = self.create_guide()
        guide = Guide.objects.get(pk=created['id'])
        for status in ('pending', 'rejected'):
            guide.current_version.status = status
            guide.current_version.save(update_fields=['status'])
            with self.subTest(status=status), self.assertRaises(ToolError):
                self.call_tool('update_guide', {
                    'guide_id': guide.pk, 'changes': {'summary': 'Cannot bypass review.'},
                    'confirm_high_impact': True,
                })
            self.assertEqual(guide.versions.count(), 1)

    def test_contributor_can_submit_prices_but_not_use_staff_batch_limits(self):
        business = Business.objects.create(name='Community Market', slug='community-market')
        product = Product.objects.create(name='Community rice', slug='community-rice')
        observation = {'product_id': product.pk, 'business_id': business.pk, 'price': '8.50'}
        created = self.call_tool('submit_price', {'observation': observation})
        report = PriceReport.objects.get(pk=created['price_report_id'])
        self.assertEqual(report.user, self.user)
        self.assertTrue(report.ai_assisted)
        with self.assertRaises(ToolError):
            self.call_tool('bulk_submit_prices', {'observations': [observation] * 26})
        self.assertEqual(PriceReport.objects.count(), 1)

    def test_contributor_cannot_attach_evidence_to_another_users_report(self):
        other = get_user_model().objects.create_user(username='other-price-author')
        business = Business.objects.create(name='Community Market', slug='community-market')
        product = Product.objects.create(name='Community rice', slug='community-rice')
        report = PriceReport.objects.create(product=product, business=business, price=8, user=other)
        buffer = io.BytesIO()
        Image.new('RGB', (16, 16), color='green').save(buffer, format='PNG')
        with self.assertRaises(ToolError):
            self.call_tool('upload_evidence', {
                'price_report_ids': [report.pk], 'image_base64': base64.b64encode(buffer.getvalue()).decode('ascii'),
                'filename': 'shelf.png',
            })
        self.assertEqual(report.photos.count(), 0)

    def test_reader_and_read_only_tokens_cannot_create_or_edit_guides(self):
        created = self.create_guide()
        read_actor = build_actor(user=self.user, token_scopes=[READ_SCOPE], client_id='read-client')
        MCPUserAccess.objects.create(user=self.user, role=MCPUserAccess.Role.READER)
        restricted_actor = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='restricted-client')
        for actor in (read_actor, restricted_actor):
            self.actor = actor
            with self.subTest(role=actor.role), self.assertRaises(ToolError):
                self.create_guide()
            with self.subTest(role=actor.role), self.assertRaises(ToolError):
                self.call_tool('update_guide', {
                    'guide_id': created['id'], 'changes': {'summary': 'Not permitted.'},
                })
        self.assertEqual(Guide.objects.count(), 1)
        self.assertEqual(GuideVersion.objects.count(), 1)


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
        self.assertEqual(code.scopes, ALL_SCOPES)

    def test_ordinary_account_can_authorize_contributions_with_normal_login(self):
        reader = get_user_model().objects.create_user(username='normal-login', password='pass')
        self.assertTrue(self.client.login(username='normal-login', password='pass'))
        consent = self.client.get(reverse('mcp_server:oauth_consent'), {'request': self.pending.pk})
        self.assertContains(consent, 'Search and read public products')
        self.assertContains(consent, 'Publish products, price observations')
        self.assertContains(consent, 'Create and update publicly visible guides')
        self.assertNotContains(consent, 'labelled on the site')
        response = self.client.post(reverse('mcp_server:oauth_consent'), {
            'request': self.pending.pk, 'action': 'approve',
        })
        self.assertEqual(response.status_code, 302)
        raw_code = parse_qs(urlparse(response['Location']).query)['code'][0]
        code = MCPOAuthAuthorizationCode.objects.get(code_hash=hash_secret(raw_code))
        self.assertEqual(code.user, reader)
        self.assertEqual(code.scopes, ALL_SCOPES)

    def test_explicit_reader_can_only_authorize_read_scope(self):
        MCPUserAccess.objects.filter(user=self.user).update(role=MCPUserAccess.Role.READER)
        self.client.force_login(self.user)
        response = self.client.post(reverse('mcp_server:oauth_consent'), {
            'request': self.pending.pk, 'action': 'approve',
        })
        self.assertEqual(response.status_code, 302)
        raw_code = parse_qs(urlparse(response['Location']).query)['code'][0]
        code = MCPOAuthAuthorizationCode.objects.get(code_hash=hash_secret(raw_code))
        self.assertEqual(code.scopes, [READ_SCOPE])

    def test_suspended_account_cannot_authorize(self):
        MCPUserAccess.objects.filter(user=self.user).update(is_active=False)
        self.client.force_login(self.user)
        response = self.client.post(reverse('mcp_server:oauth_consent'), {
            'request': self.pending.pk, 'action': 'approve',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MCPOAuthAuthorizationCode.objects.exists())

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

    def test_annotations_identify_public_writes_and_guide_overwrites(self):
        tools = {tool.name: tool for tool in async_to_sync(mcp.list_tools)()}
        read_names = {'get_schema_help', 'search_wikonomi', 'get_product', 'get_guide'}
        for name, tool in tools.items():
            with self.subTest(tool=name):
                self.assertEqual(tool.annotations.read_only_hint, name in read_names)
                self.assertEqual(tool.annotations.open_world_hint, name not in read_names)
                self.assertEqual(tool.annotations.destructive_hint, name == 'update_guide')
                self.assertNotIn('labels it AI-assisted', tool.description)
                expected_scopes = [READ_SCOPE]
                if name in {'create_guide', 'update_guide'}:
                    expected_scopes.append(PUBLISH_SCOPE)
                elif name not in read_names:
                    expected_scopes.append(WRITE_SCOPE)
                self.assertEqual(tool.meta['securitySchemes'], [
                    {'type': 'oauth2', 'scopes': expected_scopes},
                ])

    def test_price_tools_do_not_request_precise_user_location(self):
        schema = PriceObservation.model_json_schema()
        self.assertNotIn('latitude', schema['properties'])
        self.assertNotIn('longitude', schema['properties'])
        with self.assertRaises(ValidationError):
            PriceObservation(price='2.00', latitude=-9.47, longitude=147.2)


class OpenAIPluginVerificationTests(TestCase):
    def test_health_endpoint_checks_database_without_authentication(self):
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_health_failure_does_not_disclose_database_configuration(self):
        with patch('wikonomi.health.connection.cursor', side_effect=DatabaseError('private-host-marker')):
            response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b'unavailable')

    @override_settings(WIKONOMI_OPENAI_APPS_CHALLENGE='')
    def test_unconfigured_challenge_is_not_published(self):
        self.assertEqual(self.client.get(reverse('openai_apps_challenge')).status_code, 404)

    @override_settings(WIKONOMI_OPENAI_APPS_CHALLENGE='example-verification-token')
    def test_challenge_returns_exact_single_token_as_plain_text(self):
        response = self.client.get(reverse('openai_apps_challenge'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'example-verification-token')
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.client.post(reverse('openai_apps_challenge')).status_code, 405)

    @override_settings(WIKONOMI_OPENAI_APPS_CHALLENGE='token-one\ntoken-two')
    def test_multiple_tokens_are_not_exposed(self):
        self.assertEqual(self.client.get(reverse('openai_apps_challenge')).status_code, 404)
