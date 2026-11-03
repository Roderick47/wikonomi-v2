from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Business, PriceReport, Product


class ProductPageViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='product-tester', password='testpass')
        self.product = Product.objects.create(
            name='Trukai Rice 10kg',
            slug='trukai-rice-10kg',
            created_by=self.user,
        )
        self.business = Business.objects.create(name='Test Mart', slug='test-mart')
        self.other_business = Business.objects.create(name='Other Mart', slug='other-mart')
        self.stale_business = Business.objects.create(name='Old Mart', slug='old-mart')

        # Historical low at Test Mart. This must remain visible in history but
        # must not make Test Mart look cheaper than its newer K50 observation.
        self.historical_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('45.00'),
            currency='PGK',
            latitude=-9.4438,
            longitude=147.1803,
        )
        self.cheapest_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('50.00'),
            currency='PGK',
            latitude=-9.4438,
            longitude=147.1803,
        )
        self.expensive_report = PriceReport.objects.create(
            product=self.product,
            business=self.other_business,
            user=self.user,
            price=Decimal('55.00'),
            currency='PGK',
            latitude=-9.4440,
            longitude=147.1805,
        )
        # This is numerically cheaper than every current observation, but is
        # too old to be presented as the current winner.
        self.stale_report = PriceReport.objects.create(
            product=self.product,
            business=self.stale_business,
            user=self.user,
            price=Decimal('40.00'),
            currency='PGK',
            latitude=-9.4450,
            longitude=147.1810,
        )
        PriceReport.objects.filter(pk=self.stale_report.pk).update(
            observed_at=timezone.now() - timedelta(days=120)
        )
        self.stale_report.refresh_from_db()

    def test_product_list_renders_and_searches_products(self):
        response = self.client.get(reverse('product_list'), {'q': 'rice'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trukai Rice 10kg')
        self.assertContains(response, 'Search products')
        self.assertEqual(response.context['search_query'], 'rice')
        self.assertEqual(len(response.context['products_page'].object_list), 1)

    def test_product_detail_uses_latest_price_per_store_for_current_comparison(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_reports'], 4)
        self.assertEqual(response.context['current_report_count'], 3)
        self.assertEqual(response.context['comparison_store_count'], 3)
        self.assertEqual(response.context['comparable_report_count'], 2)
        self.assertEqual(response.context['comparable_store_count'], 2)
        self.assertEqual(response.context['cheapest_report'], self.cheapest_report)
        self.assertEqual(response.context['most_expensive_report'], self.expensive_report)
        self.assertNotIn(
            self.historical_report.pk,
            [report.pk for report in response.context['comparison_reports']],
        )
        self.assertIn(
            self.stale_report.pk,
            [report.pk for report in response.context['comparison_reports']],
        )
        self.assertEqual(response.context['currency_stats'][0]['currency'], 'PGK')
        self.assertEqual(response.context['currency_stats'][0]['report_count'], 3)
        self.assertEqual(response.context['comparison_savings_amount'], Decimal('5.00'))

    def test_business_detail_uses_independent_compact_summary(self):
        response = self.client.get(reverse('business_detail', args=[self.business.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="business-hero-expanded"')
        self.assertContains(response, 'id="business-hero-compact"')
        self.assertContains(response, 'Compact business summary')
        self.assertContains(response, 'Back to business details')
        self.assertContains(response, 'aria-hidden="true" inert')
        self.assertContains(response, 'default-business.svg')
        self.assertContains(response, 'data-business-id="%s"' % self.business.pk)
        self.assertNotContains(response, 'wk-business-hero-sticky')
        self.assertNotContains(response, 'business-hero-sticky-sentinel')
        self.assertNotContains(response, 'stickyHero.style.height')

    def test_price_report_detail_uses_independent_compact_summary(self):
        response = self.client.get(reverse('price_detail', args=[self.cheapest_report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="price-hero-expanded"')
        self.assertContains(response, 'id="price-hero-compact"')
        self.assertContains(response, 'data-price-compact-name')
        self.assertContains(response, 'data-price-compact-amount')
        self.assertContains(response, 'Back to price details')
        self.assertContains(response, 'aria-hidden="true" inert')
        self.assertNotContains(response, 'wk-price-hero-sticky')
        self.assertNotContains(response, 'price-hero-sticky-sentinel')
        self.assertNotContains(response, 'stickyHero.style.height')

    def test_product_detail_offers_editable_share_message(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertContains(response, '↗ Share product')
        self.assertContains(response, "kind: 'product'")
        self.assertContains(response, "preview: true")
        self.assertContains(response, 'See community-reported prices at different shops')
        self.assertNotContains(response, 'Checked this price at')

    def test_product_detail_keeps_historical_reports_in_history_feed(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        history_ids = [report.pk for report in response.context['reports_page'].object_list]
        self.assertIn(self.historical_report.pk, history_ids)
        self.assertIn(self.cheapest_report.pk, history_ids)
        self.assertIn(self.expensive_report.pk, history_ids)
        self.assertIn(self.stale_report.pk, history_ids)

    def test_product_detail_excludes_stale_price_from_current_winner(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        stale_row = next(
            report for report in response.context['comparison_reports']
            if report.pk == self.stale_report.pk
        )
        self.assertEqual(stale_row.freshness_key, 'stale')
        # Keep the comparison restriction but display the report date, not a stale badge.
        self.assertContains(response, 'Reported on')
        self.assertContains(response, 'Outside the 90-day comparison window')
        self.assertNotContains(response, '>Stale</span>')
        self.assertNotContains(response, 'Excluded — stale')
        self.assertNotEqual(response.context['cheapest_report'], self.stale_report)
        self.assertNotIn(
            self.stale_report.pk,
            [report.pk for report in response.context['nearest_reports']],
        )

    def test_product_detail_one_store_does_not_claim_multi_store_comparison(self):
        PriceReport.objects.filter(pk=self.expensive_report.pk).delete()

        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertEqual(response.context['comparable_store_count'], 1)
        self.assertFalse(response.context['comparison_has_multiple_stores'])
        self.assertIsNone(response.context['comparison_savings_amount'])
        self.assertEqual(response.context['cheapest_report'], self.cheapest_report)
        self.assertEqual(response.context['most_expensive_report'], self.cheapest_report)

    def test_product_detail_decorates_latest_known_prices_with_freshness(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        comparison_reports = response.context['comparison_reports']
        freshness_by_id = {report.pk: report.freshness_key for report in comparison_reports}
        self.assertEqual(freshness_by_id[self.cheapest_report.pk], 'fresh')
        self.assertEqual(freshness_by_id[self.expensive_report.pk], 'fresh')
        self.assertEqual(freshness_by_id[self.stale_report.pk], 'stale')

    def test_product_detail_accepts_location_sort(self):
        response = self.client.get(
            reverse('product_detail', args=[self.product.pk]),
            {'lat': '-9.4438', 'lng': '147.1803', 'sort': 'nearest'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_sort'], 'nearest')
        self.assertIsNotNone(response.context['user_lat'])
        self.assertIsNotNone(response.context['user_lng'])
        self.assertGreaterEqual(len(response.context['nearest_reports']), 1)
        nearest_ids = [report.pk for report in response.context['nearest_reports']]
        self.assertNotIn(self.stale_report.pk, nearest_ids)

    def test_product_map_includes_older_latest_known_store_prices(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        mapped_ids = [report.pk for report in response.context['reports_with_location']]
        self.assertIn(self.stale_report.pk, mapped_ids)
        self.assertIn(self.cheapest_report.pk, mapped_ids)
        self.assertNotIn(self.historical_report.pk, mapped_ids)
        self.assertContains(response, 'Where to find Trukai Rice 10kg')
        self.assertContains(response, 'id="product-map"')

    def test_product_map_has_empty_state(self):
        PriceReport.objects.all().update(latitude=None, longitude=None)
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertContains(response, 'No mapped prices yet')
        self.assertNotContains(response, 'id="product-map"')

    def test_product_detail_renders_without_reports(self):
        empty_product = Product.objects.create(
            name='Empty Product',
            slug='empty-product',
            created_by=self.user,
        )

        response = self.client.get(reverse('product_detail', args=[empty_product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No reports for this product yet')

    def test_product_analysis_page_renders(self):
        response = self.client.get(reverse('product_price_analysis', args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Advanced Price Analysis')
        self.assertContains(response, 'Price trend graph')

    def test_business_list_renders_and_searches_businesses(self):
        response = self.client.get(reverse('business_list'), {'q': 'mart'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Browse businesses on Wikonomi')
        self.assertContains(response, 'Test Mart')
        self.assertContains(response, 'Other Mart')
        self.assertContains(response, 'Old Mart')
        self.assertEqual(response.context['search_query'], 'mart')
        self.assertEqual(len(response.context['businesses_page'].object_list), 3)

    def test_business_list_empty_search_has_add_business_cta(self):
        response = self.client.get(reverse('business_list'), {'q': 'Missing Store'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No businesses found')
        self.assertContains(response, 'Add this business')
        self.assertContains(response, 'name=Missing%20Store')

    def test_product_list_empty_search_has_add_product_cta(self):
        response = self.client.get(reverse('product_list'), {'q': 'Missing Product'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No products found')
        self.assertContains(response, 'Add this product price')
        self.assertContains(response, 'product_name=Missing%20Product')
