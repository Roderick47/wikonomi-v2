"""Stage 5 interactive onboarding: actual search/map/form controls, no fake data."""
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import PriceReport


class InteractiveWalkthroughTests(TestCase):
    def test_guest_can_explore_search_and_map_without_registration(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tour-start="search"')
        self.assertContains(response, 'data-home-url=')
        self.assertContains(response, 'id="search-form"')
        self.assertContains(response, 'id="map-panel"')
        self.assertContains(response, 'id="price-feed"')
        self.assertContains(response, 'data-tour-invite hidden')
        self.assertContains(response, 'data-tour-guide hidden')
        self.assertContains(response, 'data-onboarding-open')
        self.assertNotContains(response, 'data-onboarding-slide')

    def test_price_form_preserves_real_controls_and_tour_is_optional(self):
        response = self.client.get(reverse('add_price'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tour-start="record"')
        self.assertContains(response, 'data-price-url=')
        self.assertContains(response, 'data-invite-eligible="false"')
        self.assertContains(response, 'id="photos-drop-zone"')
        self.assertContains(response, 'id="photos-input"')
        self.assertContains(response, 'id="product_search"')
        self.assertContains(response, 'id="id_price"')
        self.assertContains(response, 'id="business_search"')
        self.assertContains(response, 'id="location-details"')
        self.assertContains(response, 'name="save_action" value="finish"')

    def test_price_tour_does_not_create_test_data(self):
        before = PriceReport.objects.count()
        self.client.get(reverse('add_price'))
        self.client.get(reverse('home'))
        self.assertEqual(PriceReport.objects.count(), before)

    def test_completed_member_still_can_restart_from_help_link(self):
        user = User.objects.create_user(username='completed-tour', password='test12345')
        self.client.force_login(user)
        self.client.post(reverse('update_onboarding'), {'action': 'complete'})
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'data-invite-eligible="false"')
        self.assertContains(response, 'data-onboarding-open')
        self.assertContains(response, 'data-tour-choose')

    def test_script_has_action_driven_steps_and_no_automatic_gps(self):
        script = (Path(__file__).resolve().parent / 'static' / 'js' / 'onboarding.js').read_text()
        for target in (
            '#search-form input[name="q"]',
            '#map-panel',
            '#price-feed',
            '#photos-drop-zone',
            '#product_search',
            '#id_price',
            '#business_search',
            'saveProgress()',
            'document.addEventListener(\'submit\'',
            'document.addEventListener(\'change\'',
        ):
            self.assertIn(target, script)
        self.assertNotIn('navigator.geolocation.getCurrentPosition', script)
        self.assertNotIn('window.location.replace', script)
        self.assertNotIn("form.submit()", script)
