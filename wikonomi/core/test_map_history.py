from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth.models import User
from .models import PriceReport, Product


class MapHistoryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='map-reader')
        self.product = Product.objects.create(name='Map Rice', slug='map-rice')
        PriceReport.objects.bulk_create([
            PriceReport(product=self.product, user=self.user, price=Decimal('5'),
                        currency='PGK', observed_at=timezone.now(),
                        latitude=-9.44, longitude=147.18)
            for _ in range(503)
        ])
        self.old = PriceReport.objects.order_by('pk').first()
        PriceReport.objects.filter(pk=self.old.pk).update(updated_at=timezone.now()-timedelta(days=60))

    def test_all_batches_include_old_prices_without_duplicates(self):
        first = self.client.get('/api/map-prices/').json()
        self.assertEqual(len(first['items']), 500)
        second = self.client.get('/api/map-prices/', {'cursor': first['next_cursor']}).json()
        self.assertIsNone(second['next_cursor'])
        rows = first['items'] + second['items']
        self.assertEqual(len({r['id'] for r in rows}), 503)
        self.assertTrue(next(r for r in rows if r['id'] == self.old.pk)['is_stale'])
        self.assertEqual(sum(r['is_stale'] for r in rows), 1)

    def test_invalid_cursor_and_search(self):
        self.assertEqual(self.client.get('/api/map-prices/', {'cursor': 'bad'}).status_code, 400)
        self.assertEqual(self.client.get('/api/map-prices/', {'q': 'no-such-product'}).json()['items'], [])

    def test_old_report_stays_in_feed_and_reconfirmation_clears_stale(self):
        PriceReport.objects.exclude(pk=self.old.pk).delete()
        response = self.client.get('/')
        self.assertContains(response, 'Outdated · Check current price')
        self.assertContains(response, 'price-card--stale')
        PriceReport.objects.filter(pk=self.old.pk).update(updated_at=timezone.now())
        self.old.refresh_from_db()
        self.assertFalse(self.old.is_stale)
