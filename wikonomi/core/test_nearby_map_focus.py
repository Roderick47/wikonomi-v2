"""Regression coverage for the Nearest to Me map positioning and fallback UI."""
from django.test import TestCase
from django.urls import reverse


class NearbyMapFocusTests(TestCase):
    def test_nearest_uses_center_on_me_map_control_at_each_radius(self):
        for radius in (1, 5, 10, 25):
            with self.subTest(radius=radius):
                response = self.client.get(reverse('home'), {
                    'sort': 'nearest', 'lat': '-9.4438', 'lng': '147.1803',
                    'radius': str(radius),
                })
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'js/nearby-map-focus.js')
                self.assertContains(response, 'onclick="centerMapOnMyLocation()"')
                self.assertContains(response, 'Center on me')
                self.assertContains(response, f'<option value="{radius}" selected>', html=False)

    def test_no_local_reports_still_keep_nearest_centering_controls(self):
        response = self.client.get(reverse('home'), {
            'sort': 'nearest', 'lat': '-6.73', 'lng': '146.99', 'radius': '1',
        })
        self.assertTrue(response.context['location_fallback'])
        self.assertContains(response, 'Center on me')
        self.assertContains(response, 'showing available reports from across PNG')
        # The map keeps the national reports; the front end now centers on the
        # location pin rather than fitting distant reports into the viewport.

    def test_regular_map_keeps_near_me_button(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'onclick="handleSortChange(\'nearest\')"')
        self.assertNotContains(response, 'onclick="centerMapOnMyLocation()"')
        self.assertContains(response, 'Show all locations')
