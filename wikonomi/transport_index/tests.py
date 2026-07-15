import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import Mock, patch

import requests

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ProfileCompletionForm
from .llm_fallback import estimate_cost_usd, extract_intent
from .models import CabDriver, CabStatus, ContactAttempt, LLMFallbackLog, RouterEvent, WhatsAppMessageLog
from .router import dispatch_inbound_message
from .services import set_stale_statuses_offline
from .whatsapp_client import send_text


@override_settings(WIKONOMI_BASE_URL='https://wikonomi.com')
class TransportRouterTests(TestCase):
    def setUp(self):
        cache.clear()

    def _driver(self, phone='67570000001', verified=True, display_name='Meri Taxi'):
        driver = CabDriver.objects.create(
            whatsapp_number=phone,
            display_name=display_name,
            vehicle_type=CabDriver.VehicleType.TAXI,
            vehicle_plate='PMV123',
            home_area='Waigani',
            is_verified=verified,
        )
        CabStatus.objects.create(
            driver=driver,
            latitude=-9.443800,
            longitude=147.183600,
            availability=CabStatus.Availability.AVAILABLE,
        )
        return driver

    @patch('transport_index.router.send_text')
    def test_registered_driver_location_update_is_deterministic(self, send_text):
        driver = self._driver()
        result = dispatch_inbound_message({
            'from': driver.whatsapp_number,
            'type': 'location',
            'raw': {'location': {'latitude': -9.44, 'longitude': 147.18, 'name': 'Waigani'}},
        })

        driver.status.refresh_from_db()
        self.assertEqual(result, 'location_update')
        self.assertEqual(driver.status.availability, CabStatus.Availability.AVAILABLE)
        self.assertEqual(str(driver.status.latitude), '-9.440000')
        send_text.assert_called_once_with(driver.whatsapp_number, 'Location updated ✅')
        self.assertTrue(RouterEvent.objects.filter(stage=RouterEvent.Stage.LOCATION_UPDATE).exists())
        self.assertEqual(LLMFallbackLog.objects.count(), 0)

    @patch('transport_index.router.send_text')
    def test_driver_signup_wizard_creates_minimal_driver(self, send_text):
        phone = '67570000002'
        self.assertEqual(dispatch_inbound_message({'from': phone, 'type': 'text', 'text': 'DRIVER', 'raw': {}}), 'wizard_start')
        self.assertEqual(dispatch_inbound_message({'from': phone, 'type': 'text', 'text': 'Joe Cab', 'raw': {}}), 'wizard_step')
        self.assertEqual(dispatch_inbound_message({'from': phone, 'type': 'text', 'text': '1', 'raw': {}}), 'wizard_step')
        self.assertEqual(dispatch_inbound_message({'from': phone, 'type': 'text', 'text': 'ABC123', 'raw': {}}), 'wizard_step')

        driver = CabDriver.objects.get(whatsapp_number=phone)
        self.assertEqual(driver.display_name, 'Joe Cab')
        self.assertEqual(driver.vehicle_type, CabDriver.VehicleType.TAXI)
        self.assertEqual(driver.vehicle_plate, 'ABC123')
        self.assertEqual(driver.profile_completeness, CabDriver.ProfileCompleteness.MINIMAL)
        self.assertEqual(driver.status.availability, CabStatus.Availability.OFFLINE)
        self.assertIn('/cabs/setup/', send_text.call_args_list[-1].args[1])
        self.assertEqual(LLMFallbackLog.objects.count(), 0)

    @patch('transport_index.router.send_text')
    @patch('transport_index.router.send_interactive_list')
    def test_rider_location_returns_verified_contact_proxy_links(self, send_interactive_list, send_text):
        verified = self._driver(phone='67570000003', verified=True, display_name='Verified Taxi')
        unverified = self._driver(phone='67570000004', verified=False, display_name='Unverified Taxi')

        result = dispatch_inbound_message({
            'from': '67579999999',
            'type': 'location',
            'raw': {'location': {'latitude': -9.4437, 'longitude': 147.1835}},
        })

        self.assertEqual(result, 'rider_location')
        send_interactive_list.assert_called_once()
        link_message = send_text.call_args.args[1]
        self.assertIn(reverse('transport_index:cab_contact', args=[verified.slug]), link_message)
        self.assertNotIn(verified.whatsapp_number, link_message)
        self.assertNotIn(unverified.display_name, link_message)
        self.assertTrue(RouterEvent.objects.filter(stage=RouterEvent.Stage.RIDER_LOCATION).exists())
        self.assertEqual(LLMFallbackLog.objects.count(), 0)

    @patch('transport_index.router.send_text')
    @patch('transport_index.router.send_interactive_list')
    def test_gazetteer_hit_avoids_llm(self, send_interactive_list, send_text):
        self._driver(phone='67570000005', verified=True)
        result = dispatch_inbound_message({
            'from': '67578888888',
            'type': 'text',
            'text': 'waigani',
            'raw': {},
        })

        self.assertEqual(result, 'gazetteer_hit')
        send_interactive_list.assert_called_once()
        self.assertTrue(RouterEvent.objects.filter(stage=RouterEvent.Stage.GAZETTEER_HIT).exists())
        self.assertEqual(LLMFallbackLog.objects.count(), 0)

    @patch('transport_index.router.send_text')
    @patch('transport_index.llm_fallback.extract_intent', return_value={'intent': 'unknown', 'place': ''})
    def test_llm_fallback_is_only_final_route(self, extract_intent, send_text):
        result = dispatch_inbound_message({
            'from': '67577777777',
            'type': 'text',
            'text': 'something ambiguous with no known place',
            'raw': {},
        })

        self.assertEqual(result, 'llm_fallback')
        extract_intent.assert_called_once()
        self.assertTrue(RouterEvent.objects.filter(stage=RouterEvent.Stage.LLM_FALLBACK).exists())


class TransportViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.verified = CabDriver.objects.create(
            whatsapp_number='67570000010',
            display_name='Verified Driver',
            vehicle_type=CabDriver.VehicleType.PMV,
            vehicle_plate='VFY123',
            home_area='Boroko',
            bio='Reliable PMV.',
            is_verified=True,
        )
        CabStatus.objects.create(driver=self.verified, availability=CabStatus.Availability.AVAILABLE)
        self.unverified = CabDriver.objects.create(
            whatsapp_number='67570000011',
            display_name='Unverified Driver',
            vehicle_type=CabDriver.VehicleType.TAXI,
            vehicle_plate='UNV123',
            is_verified=False,
        )
        CabStatus.objects.create(driver=self.unverified, availability=CabStatus.Availability.AVAILABLE)

    def test_listing_shows_only_verified_drivers_and_no_phone_numbers(self):
        response = self.client.get(reverse('transport_index:cab_list'))

        self.assertContains(response, self.verified.display_name)
        self.assertNotContains(response, self.unverified.display_name)
        self.assertNotContains(response, self.verified.whatsapp_number)
        self.assertNotContains(response, self.unverified.whatsapp_number)

    def test_unverified_profile_is_directly_reachable_without_phone_in_source(self):
        response = self.client.get(reverse('transport_index:cab_profile', args=[self.unverified.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.unverified.display_name)
        self.assertNotContains(response, self.unverified.whatsapp_number)

    def test_contact_proxy_logs_attempt_and_redirects_to_whatsapp(self):
        response = self.client.get(
            reverse('transport_index:cab_contact', args=[self.verified.slug]),
            HTTP_USER_AGENT='Test Browser',
            REMOTE_ADDR='203.0.113.8',
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(f'https://wa.me/{self.verified.whatsapp_number}'))
        attempt = ContactAttempt.objects.get(driver=self.verified)
        self.assertEqual(attempt.ip_address, '203.0.113.8')
        self.assertEqual(attempt.user_agent, 'Test Browser')

    def test_robots_txt_blocks_contact_paths(self):
        response = self.client.get(reverse('robots_txt'))

        self.assertContains(response, 'Disallow: /cabs/*/contact/')
        self.assertContains(response, 'Allow: /cabs/')


class WhatsAppWebhookTests(TestCase):
    def _payload(self):
        return {
            'entry': [{
                'changes': [{
                    'value': {
                        'metadata': {'phone_number_id': '123'},
                        'contacts': [{'wa_id': '67570000020', 'profile': {'name': 'Tester'}}],
                        'messages': [{'from': '67570000020', 'id': 'wamid.1', 'type': 'text', 'text': {'body': 'find cab'}}],
                    },
                }],
            }],
        }

    @override_settings(WHATSAPP_WEBHOOK_VERIFY_TOKEN='verify-me')
    def test_webhook_get_verification(self):
        response = self.client.get(reverse('transport_index:whatsapp_webhook'), {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'verify-me',
            'hub.challenge': 'challenge-123',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'challenge-123')

    @override_settings(WHATSAPP_APP_SECRET='secret')
    @patch('transport_index.views.dispatch_inbound_message')
    def test_webhook_rejects_invalid_signature(self, dispatch):
        body = json.dumps(self._payload()).encode('utf-8')
        response = self.client.post(
            reverse('transport_index:whatsapp_webhook'),
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=bad',
        )

        self.assertEqual(response.status_code, 403)
        dispatch.assert_not_called()

    @override_settings(WHATSAPP_APP_SECRET='secret')
    @patch('transport_index.views.dispatch_inbound_message')
    def test_webhook_accepts_valid_signature_and_dispatches(self, dispatch):
        body = json.dumps(self._payload()).encode('utf-8')
        signature = hmac.new(b'secret', body, hashlib.sha256).hexdigest()
        response = self.client.post(
            reverse('transport_index:whatsapp_webhook'),
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=f'sha256={signature}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['dispatched'], 1)
        dispatch.assert_called_once()


class StaleStatusTests(TestCase):
    def test_set_stale_statuses_offline_only_updates_old_available_statuses(self):
        stale_driver = CabDriver.objects.create(
            whatsapp_number='67570000030',
            display_name='Stale Driver',
            vehicle_type=CabDriver.VehicleType.TAXI,
            vehicle_plate='OLD123',
        )
        fresh_driver = CabDriver.objects.create(
            whatsapp_number='67570000031',
            display_name='Fresh Driver',
            vehicle_type=CabDriver.VehicleType.TAXI,
            vehicle_plate='NEW123',
        )
        stale_status = CabStatus.objects.create(driver=stale_driver, availability=CabStatus.Availability.AVAILABLE)
        fresh_status = CabStatus.objects.create(driver=fresh_driver, availability=CabStatus.Availability.AVAILABLE)
        CabStatus.objects.filter(id=stale_status.id).update(last_updated=timezone.now() - timezone.timedelta(minutes=25))

        self.assertEqual(set_stale_statuses_offline(minutes=20), 1)
        stale_status.refresh_from_db()
        fresh_status.refresh_from_db()
        self.assertEqual(stale_status.availability, CabStatus.Availability.OFFLINE)
        self.assertEqual(fresh_status.availability, CabStatus.Availability.AVAILABLE)


class PriorityTwoObservabilityTests(TestCase):
    @override_settings(
        WHATSAPP_TOKEN='token',
        WHATSAPP_PHONE_NUMBER_ID='phone-id',
        WHATSAPP_API_VERSION='v22.0',
    )
    @patch('transport_index.whatsapp_client.requests.post')
    def test_successful_whatsapp_send_is_logged(self, post):
        response = Mock()
        response.json.return_value = {'messages': [{'id': 'wamid.test'}]}
        response.raise_for_status.return_value = None
        post.return_value = response

        send_text('67570000040', 'Hello')

        log = WhatsAppMessageLog.objects.get()
        self.assertEqual(log.recipient, '67570000040')
        self.assertEqual(log.message_type, 'text')
        self.assertEqual(log.status, WhatsAppMessageLog.Status.SENT)
        self.assertEqual(log.response['messages'][0]['id'], 'wamid.test')

    @override_settings(
        WHATSAPP_TOKEN='token',
        WHATSAPP_PHONE_NUMBER_ID='phone-id',
        WHATSAPP_API_VERSION='v22.0',
    )
    @patch('transport_index.whatsapp_client.requests.post')
    def test_failed_whatsapp_send_is_logged(self, post):
        response = Mock()
        response.text = 'bad request'
        response.json.side_effect = ValueError('not json')
        error = requests.HTTPError('400 Client Error')
        error.response = response
        response.raise_for_status.side_effect = error
        post.return_value = response

        with self.assertRaises(requests.HTTPError):
            send_text('67570000041', 'Hello')

        log = WhatsAppMessageLog.objects.get()
        self.assertEqual(log.recipient, '67570000041')
        self.assertEqual(log.status, WhatsAppMessageLog.Status.FAILED)
        self.assertEqual(log.response, {'body': 'bad request'})
        self.assertIn('400 Client Error', log.error)

    @override_settings()
    def test_llm_cost_estimate_uses_configured_rates(self):
        with patch.dict('os.environ', {
            'ANTHROPIC_HAIKU_INPUT_COST_PER_MILLION': '1.00',
            'ANTHROPIC_HAIKU_OUTPUT_COST_PER_MILLION': '5.00',
        }):
            self.assertEqual(estimate_cost_usd(1000, 2000), Decimal('0.011'))

    @patch('transport_index.llm_fallback.requests.post')
    def test_llm_fallback_logs_estimated_cost(self, post):
        response = Mock()
        response.json.return_value = {
            'content': [{'type': 'text', 'text': '{"intent": "find_cab", "place": "Waigani"}'}],
            'usage': {'input_tokens': 1000, 'output_tokens': 2000},
        }
        response.raise_for_status.return_value = None
        post.return_value = response

        with patch.dict('os.environ', {
            'ANTHROPIC_API_KEY': 'test-key',
            'ANTHROPIC_HAIKU_INPUT_COST_PER_MILLION': '1.00',
            'ANTHROPIC_HAIKU_OUTPUT_COST_PER_MILLION': '5.00',
        }):
            extracted = extract_intent('Need taxi near Waigani')

        self.assertEqual(extracted['intent'], 'find_cab')
        log = LLMFallbackLog.objects.get()
        self.assertEqual(log.input_tokens, 1000)
        self.assertEqual(log.output_tokens, 2000)
        self.assertEqual(log.estimated_cost_usd, Decimal('0.011000'))

    def test_router_event_admin_dashboard_renders_observability_counts(self):
        user = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.force_login(user)
        RouterEvent.objects.create(phone_number='67570000042', stage=RouterEvent.Stage.KEYWORD_MATCH, message_type='text')
        WhatsAppMessageLog.objects.create(
            recipient='67570000042',
            message_type='text',
            status=WhatsAppMessageLog.Status.SENT,
        )
        LLMFallbackLog.objects.create(input_text='hello', extracted_intent='unknown', estimated_cost_usd=Decimal('0.005'))

        response = self.client.get('/admin/transport_index/routerevent/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'keyword_match')
        self.assertContains(response, 'sent')
        self.assertContains(response, '0.005')


class PriorityThreeUXTests(TestCase):
    def _create_driver(self, index):
        driver = CabDriver.objects.create(
            whatsapp_number=f'6757010{index:04d}',
            display_name=f'Paged Driver {index:02d}',
            vehicle_type=CabDriver.VehicleType.TAXI,
            vehicle_plate=f'PG{index:03d}',
            home_area='Waigani',
            is_verified=True,
        )
        CabStatus.objects.create(driver=driver, availability=CabStatus.Availability.AVAILABLE)
        return driver

    def test_cab_list_is_paginated_and_site_integrated(self):
        for index in range(13):
            self._create_driver(index)

        response = self.client.get(reverse('transport_index:cab_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'wikonomi')
        self.assertContains(response, 'Sort by my location')
        self.assertContains(response, 'Page 1 of 2')
        self.assertContains(response, 'Paged Driver 00')
        self.assertNotContains(response, 'Paged Driver 12')

    def test_cab_list_second_page_preserves_results(self):
        for index in range(13):
            self._create_driver(index)

        response = self.client.get(reverse('transport_index:cab_list'), {'page': '2'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paged Driver 12')
        self.assertContains(response, 'Page 2 of 2')

    def test_profile_completion_form_rejects_large_images(self):
        upload = SimpleUploadedFile('profile.jpg', b'a' * (5 * 1024 * 1024 + 1), content_type='image/jpeg')
        form = ProfileCompletionForm(files={'profile_photo': upload}, data={'bio': 'Hello', 'home_area': 'Waigani'})

        self.assertFalse(form.is_valid())
        self.assertIn('profile_photo', form.errors)

    def test_profile_completion_form_rejects_non_image_content_type(self):
        upload = SimpleUploadedFile('profile.txt', b'not an image', content_type='text/plain')
        form = ProfileCompletionForm(files={'profile_photo': upload}, data={'bio': 'Hello', 'home_area': 'Waigani'})

        self.assertFalse(form.is_valid())
        self.assertIn('profile_photo', form.errors)
