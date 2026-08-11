from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class TransportIndexAccessTests(TestCase):
    def test_public_user_sees_coming_soon_page(self):
        response = self.client.get(reverse('transport_index:index'))

        self.assertContains(response, 'Coming soon')
        self.assertContains(response, 'WhatsApp AI chat')
        self.assertTemplateUsed(response, 'transport_index/coming_soon.html')

    def test_staff_user_sees_admin_preview(self):
        user = get_user_model().objects.create_user(
            username='transport-admin',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('transport_index:index'))

        self.assertContains(response, 'Administrator preview')
        self.assertTemplateUsed(response, 'transport_index/index.html')

    def test_legacy_cabs_url_redirects_to_transport(self):
        response = self.client.get('/cabs/')

        self.assertRedirects(response, '/transport/', status_code=301)

    def test_transport_url_is_canonical_route(self):
        self.assertEqual(reverse('transport_index:index'), '/transport/')
