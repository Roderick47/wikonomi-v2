from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import Business, PriceReport, Product
from mcp_server.current_price_services import get_product, search_wikonomi


class MCPCurrentPriceReadTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mcp-price-reader', password='testpass123')
        self.store_a = Business.objects.create(name='MCP Store A', slug='mcp-store-a')
        self.store_b = Business.objects.create(name='MCP Store B', slug='mcp-store-b')
        self.product = Product.objects.create(
            name='MCP Rice 1kg',
            slug='mcp-rice-1kg',
            created_by=self.user,
        )

    def _price(self, business, price, days_old=0):
        report = PriceReport.objects.create(
            product=self.product,
            business=business,
            user=self.user,
            price=Decimal(str(price)),
            currency='PGK',
        )
        if days_old:
            PriceReport.objects.filter(pk=report.pk).update(
                observed_at=timezone.now() - timedelta(days=days_old)
            )
            report.refresh_from_db()
        return report

    def test_newer_store_price_replaces_old_historical_low(self):
        self._price(self.store_a, '5.00', days_old=20)
        newest = self._price(self.store_a, '10.00')
        other = self._price(self.store_b, '8.00')

        payload = get_product(self.product.pk)

        current = payload['current_comparison']
        self.assertEqual(current['min_price'], '8.00')
        self.assertEqual(current['max_price'], '10.00')
        self.assertEqual(current['comparable_store_count'], 2)
        self.assertEqual(current['best_price']['id'], other.pk)
        self.assertIn(newest.pk, [row['id'] for row in current['latest_known_prices']])

        history = payload['historical_statistics']
        self.assertEqual(history['min_price'], '5.00')
        self.assertEqual(history['count'], 3)

    def test_stale_latest_store_price_is_visible_but_cannot_win(self):
        stale = self._price(self.store_a, '4.00', days_old=120)
        fresh = self._price(self.store_b, '9.00')

        payload = get_product(self.product.pk)
        current = payload['current_comparison']

        self.assertEqual(current['latest_known_store_count'], 2)
        self.assertEqual(current['comparable_store_count'], 1)
        self.assertEqual(current['stale_excluded_count'], 1)
        self.assertEqual(current['best_price']['id'], fresh.pk)
        stale_row = next(row for row in current['latest_known_prices'] if row['id'] == stale.pk)
        self.assertEqual(stale_row['freshness'], 'stale')

    def test_search_labels_current_prices_separately_from_history(self):
        self._price(self.store_a, '5.00', days_old=20)
        self._price(self.store_a, '10.00')
        self._price(self.store_b, '8.00')

        payload = search_wikonomi('MCP Rice', ['product'], 10)

        self.assertEqual(payload['count'], 1)
        result = payload['results'][0]
        self.assertNotIn('price_range', result)
        self.assertEqual(result['historical_price_count'], 3)
        self.assertEqual(result['current_price_summary']['min_price'], '8.00')
        self.assertEqual(result['current_price_summary']['comparable_store_count'], 2)
