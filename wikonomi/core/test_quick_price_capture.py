"""Regression tests for the mobile-first price recording flow."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Business, PriceReport, Product


class QuickPriceCaptureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='quick-price-tester', password='testpass')
        cls.product = Product.objects.create(name='Quick Rice', slug='quick-rice', created_by=cls.user)
        cls.business = Business.objects.create(name='Sample Shop', slug='sample-shop')
        # An existing business location should be reused on subsequent reports.
        PriceReport.objects.create(
            user=cls.user, product=cls.product, business=cls.business,
            price=Decimal('5.50'), currency='PGK',
            latitude=-9.4438, longitude=147.1803,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_quick_price_form_keeps_original_fields_and_photo_capture(self):
        response = self.client.get(reverse('add_price'))
        self.assertEqual(response.status_code, 200)
        for value in (
            'name="product_name"',
            'name="business_name"',
            'name="photos"',
            'capture',
            'data-wk-validate',
            'id="location-details"',
            'id="advanced-details"',
            'name="save_action" value="another"',
            'name="save_action" value="finish"',
            'Choose photo',
            'Take photo',
        ):
            self.assertContains(response, value)
        # Optional categories and location remain supported.
        self.assertContains(response, 'id="id_category"')
        self.assertContains(response, 'id="id_subcategory"')
        self.assertContains(response, 'id="id_latitude"')
        self.assertContains(response, 'id="id_longitude"')

    @patch('core.views.ProductNormalizationService.normalize_price_report_data')
    def test_save_price_without_optional_photo_or_shop(self, normalize):
        normalize.return_value = (self.product, False)
        response = self.client.post(reverse('add_price'), {
            'product_name': 'Quick Rice',
            'price': '4.50',
            'currency': 'PGK',
            'save_action': 'finish',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertTrue(PriceReport.objects.filter(
            user=self.user, product=self.product, price=Decimal('4.50'),
        ).exists())

    @patch('core.views.BusinessNormalizationService.normalize_price_report_data')
    @patch('core.views.ProductNormalizationService.normalize_price_report_data')
    def test_save_and_add_another_prefills_shop(self, normalize_product, normalize_business):
        normalize_product.return_value = (self.product, False)
        normalize_business.return_value = (self.business, None, False)
        response = self.client.post(reverse('add_price'), {
            'product_name': 'Quick Rice',
            'business_name': 'Sample Shop',
            'price': '4.75',
            'currency': 'PGK',
            'save_action': 'another',
        })
        next_url = reverse('add_price') + '?business_name=Sample+Shop'
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        saved = PriceReport.objects.filter(price=Decimal('4.75')).get()
        self.assertEqual((saved.latitude, saved.longitude), (-9.4438, 147.1803))
        followup = self.client.get(response.url)
        self.assertContains(followup, 'value="Sample Shop"')

    def test_invalid_submission_retains_manual_fields_and_opens_details(self):
        response = self.client.post(reverse('add_price'), {
            'product_name': 'Entered Milk',
            'business_name': 'New Local Shop',
            'tags': 'milk, grocery',
            'price': '-1',
            'currency': 'PGK',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Entered Milk"')
        self.assertContains(response, 'value="New Local Shop"')
        self.assertContains(response, 'value="milk, grocery"')
        self.assertContains(response, 'id="location-details"')
        self.assertContains(response, 'id="advanced-details"')
        self.assertContains(response, 'Please correct the errors below.')

    @patch('core.views.BusinessNormalizationService.normalize_price_report_data')
    @patch('core.views.ProductNormalizationService.normalize_price_report_data')
    def test_new_shop_without_location_still_needs_a_map_pin(self, normalize_product, normalize_business):
        unlocated = Business.objects.create(name='New Local Shop', slug='new-local-shop')
        normalize_product.return_value = (self.product, False)
        normalize_business.return_value = (unlocated, None, False)
        response = self.client.post(reverse('add_price'), {
            'product_name': 'Quick Rice',
            'business_name': 'New Local Shop',
            'price': '3.00',
            'currency': 'PGK',
            'save_action': 'another',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please set a location for this price')
        self.assertFalse(PriceReport.objects.filter(business=unlocated).exists())
        self.assertContains(response, 'value="New Local Shop"')
