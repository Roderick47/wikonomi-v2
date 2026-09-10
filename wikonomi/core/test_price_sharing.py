from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Business, PriceReport, Product
from .share_services import build_price_share_context


class EnrichedPriceSharingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='share-tester', password='testpass')
        self.product = Product.objects.create(name='Test Rice 1kg', slug='test-rice-1kg')
        self.store_a = Business.objects.create(name='Store A', slug='store-a')
        self.store_b = Business.objects.create(name='Store B', slug='store-b')
        self.store_c = Business.objects.create(name='Store C', slug='store-c')

    def make_report(self, *, store, price, days_old=0, currency='PGK', marked=False):
        report = PriceReport.objects.create(
            product=self.product,
            business=store,
            user=self.user,
            price=Decimal(str(price)),
            currency=currency,
            marked_for_deletion=marked,
        )
        if days_old:
            observed_at = timezone.now() - timedelta(days=days_old)
            PriceReport.objects.filter(pk=report.pk).update(observed_at=observed_at)
            report.refresh_from_db()
        return report

    def test_current_non_cheapest_share_uses_best_current_price_and_gap(self):
        shared = self.make_report(store=self.store_a, price='12.00')
        self.make_report(store=self.store_b, price='10.00')
        self.make_report(store=self.store_c, price='15.00')

        data = build_price_share_context(shared, base_url='https://www.wikonomi.com')

        self.assertTrue(data['is_current_comparable'])
        self.assertEqual(data['store_count'], 3)
        self.assertEqual(data['best_current_price'], '10.00')
        self.assertEqual(data['best_current_store'], 'Store B')
        self.assertEqual(data['gap_from_best'], '2.00')
        self.assertEqual(Decimal(data['gap_percent']).quantize(Decimal('0.1')), Decimal('20.0'))
        self.assertIn('Best current Wikonomi price: PGK 10.00 at Store B.', data['text'])
        self.assertIn('PGK 2.00 (20.0%) higher', data['text'])
        self.assertIn('/price/', data['share_url'])
        self.assertTrue(data['share_url'].endswith('/share/'))

    def test_cheapest_current_share_surfaces_saving_vs_highest_current_price(self):
        shared = self.make_report(store=self.store_a, price='10.00')
        self.make_report(store=self.store_b, price='12.00')
        self.make_report(store=self.store_c, price='15.00')

        data = build_price_share_context(shared)

        self.assertTrue(data['is_current_comparable'])
        self.assertEqual(data['store_count'], 3)
        self.assertEqual(data['savings_amount'], '5.00')
        self.assertEqual(Decimal(data['savings_percent']).quantize(Decimal('0.1')), Decimal('33.3'))
        self.assertIn('Lowest current Wikonomi price across 3 stores', data['comparison_line'])
        self.assertIn('save up to PGK 5.00 (33.3%)', data['comparison_line'])

    def test_older_shared_report_never_becomes_current_winner(self):
        old_shared = self.make_report(store=self.store_a, price='8.00', days_old=10)
        self.make_report(store=self.store_a, price='12.00', days_old=1)
        self.make_report(store=self.store_b, price='9.00', days_old=2)

        data = build_price_share_context(old_shared)

        self.assertFalse(data['is_latest_store_observation'])
        self.assertFalse(data['is_current_comparable'])
        self.assertEqual(data['best_current_price'], '9.00')
        self.assertIn('This is an older observation.', data['status_line'])
        self.assertIn('Latest known at Store A: PGK 12.00', data['status_line'])
        self.assertIn('Current best: PGK 9.00 at Store B across 2 stores.', data['comparison_line'])
        self.assertNotIn('Lowest current Wikonomi price', data['comparison_line'])

    def test_stale_latest_report_is_excluded_from_current_cheapest_ranking(self):
        stale_shared = self.make_report(store=self.store_a, price='5.00', days_old=120)
        self.make_report(store=self.store_b, price='10.00', days_old=2)

        data = build_price_share_context(stale_shared)

        self.assertEqual(data['freshness_key'], 'stale')
        self.assertTrue(data['is_latest_store_observation'])
        self.assertFalse(data['is_current_comparable'])
        self.assertEqual(data['store_count'], 1)
        self.assertEqual(data['best_current_price'], '10.00')
        self.assertIn('excluded from the current cheapest ranking', data['status_line'])
        self.assertIn('Only one current store price is available: PGK 10.00 at Store B.', data['comparison_line'])

    def test_single_current_store_says_there_is_no_store_to_store_comparison(self):
        shared = self.make_report(store=self.store_a, price='11.50')

        data = build_price_share_context(shared)

        self.assertEqual(data['store_count'], 1)
        self.assertTrue(data['is_current_comparable'])
        self.assertIn('Only one current store price is available', data['comparison_line'])
        self.assertIn('no store-to-store comparison yet', data['comparison_line'])

    def test_marked_report_is_explicitly_excluded(self):
        shared = self.make_report(store=self.store_a, price='7.00', marked=True)
        self.make_report(store=self.store_b, price='9.00')

        data = build_price_share_context(shared)

        self.assertFalse(data['is_current_comparable'])
        self.assertIn('marked for deletion', data['status_line'])
        self.assertIn('excluded from current price comparisons', data['status_line'])

    def test_different_currencies_are_not_mixed_in_share_comparison(self):
        shared = self.make_report(store=self.store_a, price='4.00', currency='USD')
        self.make_report(store=self.store_b, price='10.00', currency='PGK')

        data = build_price_share_context(shared)

        self.assertEqual(data['currency'], 'USD')
        self.assertEqual(data['store_count'], 1)
        self.assertEqual(data['best_current_price'], '4.00')
        self.assertNotIn('PGK 10.00', data['comparison_line'])

    def test_share_landing_page_has_enriched_preview_and_comparison_link(self):
        shared = self.make_report(store=self.store_a, price='10.00')
        self.make_report(store=self.store_b, price='15.00')

        response = self.client.get(reverse('price_share', args=[shared.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shared price')
        self.assertContains(response, 'Lowest current Wikonomi price across 2 stores')
        self.assertContains(response, 'Potential saving')
        self.assertContains(response, reverse('price_detail', args=[shared.pk]))
        self.assertContains(response, reverse('product_detail', args=[self.product.pk]))
        self.assertContains(response, 'og:description')
        self.assertContains(response, reverse('price_share', args=[shared.pk]))

    def test_share_data_endpoint_returns_the_same_current_summary(self):
        shared = self.make_report(store=self.store_a, price='12.00')
        self.make_report(store=self.store_b, price='10.00')

        response = self.client.get(reverse('price_share_data', args=[shared.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['store_count'], 2)
        self.assertEqual(payload['best_current_price'], '10.00')
        self.assertEqual(payload['gap_from_best'], '2.00')
        self.assertIn('/share/', payload['share_url'])
