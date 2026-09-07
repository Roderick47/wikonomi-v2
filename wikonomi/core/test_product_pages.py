from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

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
        self.assertEqual(response.context['total_reports'], 3)
        self.assertEqual(response.context['current_report_count'], 2)
        self.assertEqual(response.context['comparison_store_count'], 2)
        self.assertEqual(response.context['cheapest_report'], self.cheapest_report)
        self.assertEqual(response.context['most_expensive_report'], self.expensive_report)
        self.assertNotIn(
            self.historical_report.pk,
            [report.pk for report in response.context['comparison_reports']],
        )
        self.assertEqual(response.context['currency_stats'][0]['currency'], 'PGK')
        self.assertEqual(response.context['currency_stats'][0]['report_count'], 2)
        self.assertEqual(response.context['comparison_savings_amount'], Decimal('5.00'))

    def test_product_detail_keeps_historical_reports_in_history_feed(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        history_ids = [report.pk for report in response.context['reports_page'].object_list]
        self.assertIn(self.historical_report.pk, history_ids)
        self.assertIn(self.cheapest_report.pk, history_ids)
        self.assertIn(self.expensive_report.pk, history_ids)

    def test_product_detail_one_store_does_not_claim_multi_store_comparison(self):
        PriceReport.objects.filter(pk=self.expensive_report.pk).delete()

        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertEqual(response.context['comparison_store_count'], 1)
        self.assertFalse(response.context['comparison_has_multiple_stores'])
        self.assertIsNone(response.context['comparison_savings_amount'])
        self.assertEqual(response.context['cheapest_report'], self.cheapest_report)
        self.assertEqual(response.context['most_expensive_report'], self.cheapest_report)

    def test_product_detail_decorates_current_prices_with_freshness(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        comparison_reports = response.context['comparison_reports']
        self.assertTrue(comparison_reports)
        self.assertTrue(all(hasattr(report, 'freshness_key') for report in comparison_reports))
        self.assertTrue(all(report.freshness_key == 'fresh' for report in comparison_reports))

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
        self.assertEqual(response.context['search_query'], 'mart')
        self.assertEqual(len(response.context['businesses_page'].object_list), 2)

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
