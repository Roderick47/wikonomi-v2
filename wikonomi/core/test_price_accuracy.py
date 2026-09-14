from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import STALE_PRICE_DAYS, PriceLike, PriceReport, Product


class PriceAccuracyConfirmationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='price-owner', password='testpass')
        self.voter = User.objects.create_user(username='price-voter', password='testpass')
        self.product = Product.objects.create(
            name='Accuracy Test Product',
            slug='accuracy-test-product',
            created_by=self.owner,
        )
        self.report = PriceReport.objects.create(
            product=self.product,
            user=self.owner,
            price=Decimal('10.00'),
            currency='PGK',
        )
        self._make_report_stale()
        self.client.force_login(self.voter)

    def _make_report_stale(self):
        stale_time = timezone.now() - timedelta(days=STALE_PRICE_DAYS + 1)
        PriceReport.objects.filter(pk=self.report.pk).update(updated_at=stale_time)
        self.report.refresh_from_db()

    def test_yes_confirmation_clears_stale_status(self):
        self.assertTrue(self.report.is_stale)

        response = self.client.post(reverse('toggle_price_like', args=[self.report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PriceLike.objects.filter(user=self.voter, price_report=self.report).exists())
        self.report.refresh_from_db()
        self.assertFalse(self.report.is_stale)

    def test_removing_yes_does_not_refresh_stale_report(self):
        self.client.post(reverse('toggle_price_like', args=[self.report.pk]))
        self._make_report_stale()

        response = self.client.post(reverse('toggle_price_like', args=[self.report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PriceLike.objects.filter(user=self.voter, price_report=self.report).exists())
        self.report.refresh_from_db()
        self.assertTrue(self.report.is_stale)
