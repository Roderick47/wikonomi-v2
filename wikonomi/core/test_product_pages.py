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
        self.cheapest_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('45.00'),
            currency='PGK',
            latitude=-9.4438,
            longitude=147.1803,
        )
        self.expensive_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
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

    def test_product_detail_aggregates_reports(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aggregated price reports')
        self.assertEqual(response.context['total_reports'], 2)
        self.assertEqual(response.context['cheapest_report'], self.cheapest_report)
        self.assertEqual(response.context['most_expensive_report'], self.expensive_report)
        self.assertEqual(response.context['currency_stats'][0]['currency'], 'PGK')
        self.assertEqual(response.context['currency_stats'][0]['report_count'], 2)

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
