"""Homepage discovery ranking and location fallback regression tests."""
import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Business, PriceReport, Product


class DiscoveryFeedTests(TestCase):
    def setUp(self):
        cache.clear()

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='discovery-tester')
        cls.product = Product.objects.create(name='Discovery Rice', slug='discovery-rice')
        cls.busy = Business.objects.create(name='Busy Mart', slug='busy-mart')
        cls.second = Business.objects.create(name='Second Mart', slug='second-mart')
        cls.third = Business.objects.create(name='Third Mart', slug='third-mart')

        # Older reports from other shops, then a recent bulk upload from one shop.
        for shop in (cls.second, cls.third):
            PriceReport.objects.create(
                user=cls.user, product=cls.product, business=shop,
                price=Decimal('6.00'), currency='PGK',
            )
        for i in range(24):
            PriceReport.objects.create(
                user=cls.user, product=cls.product, business=cls.busy,
                price=Decimal('7.00') + Decimal(i) / 100,
                currency='PGK',
            )

    def test_discovery_promotes_multiple_stores_into_first_screen(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_sort'], 'discover')
        cards = response.context['latest_prices']
        self.assertEqual(len(cards), 20)
        self.assertEqual(len({r.business_id for r in cards[:3]}), 3)
        self.assertContains(response, 'Explore reported prices')
        self.assertContains(response, 'Explore different shops')

    def test_default_search_diversifies_stores_too(self):
        response = self.client.get(reverse('home'), {'q': 'Discovery Rice'})
        cards = response.context['latest_prices']
        self.assertEqual(len({row.business_id for row in cards[:3]}), 3)
        self.assertEqual(response.context['current_sort'], 'discover')

    def test_latest_sort_remains_strictly_chronological(self):
        response = self.client.get(reverse('home'), {'sort': 'recent'})
        self.assertEqual(response.context['current_sort'], 'recent')
        cards = response.context['latest_prices']
        self.assertTrue(all(r.business_id == self.busy.pk for r in cards))
        self.assertEqual(
            [r.observed_at for r in cards],
            sorted((r.observed_at for r in cards), reverse=True),
        )

    def test_all_pages_use_same_discovery_order_without_duplicates(self):
        homepage = self.client.get(reverse('home'))
        first_ids = [row.pk for row in homepage.context['latest_prices']]

        more = self.client.get(reverse('load_more_prices'), {'page': 2}).json()
        second_ids = []
        for card in more['items']:
            match = re.search(r'data-object-id="(\d+)"', card)
            self.assertIsNotNone(match)
            second_ids.append(int(match.group(1)))

        self.assertEqual(len(first_ids), 20)
        self.assertEqual(len(second_ids), 6)
        self.assertEqual(len(set(first_ids + second_ids)), 26)
        self.assertEqual(set(first_ids + second_ids), set(PriceReport.objects.values_list('id', flat=True)))
        self.assertFalse(more['has_more'])

    def test_mapped_home_cards_link_back_to_the_map(self):
        mapped = PriceReport.objects.create(
            user=self.user, product=self.product, business=self.second,
            price=Decimal('8.00'), currency='PGK',
            latitude=-9.443, longitude=147.18,
        )
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'View on map')
        self.assertContains(response, f'data-map-report-id="{mapped.pk}"')

    def test_nearest_with_no_local_reports_falls_back_to_discovery(self):
        # The prices in this fixture have no coordinates. An empty 'nearest'
        # view must not hide the existing national price archive.
        response = self.client.get(reverse('home'), {
            'sort': 'nearest', 'lat': '-6.73', 'lng': '146.99',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['location_fallback'])
        self.assertEqual(response.context['current_sort'], 'discover')
        self.assertEqual(len(response.context['latest_prices']), 20)
        self.assertContains(response, 'showing available reports from across PNG')

    def test_nearby_reports_preferred_when_location_is_available(self):
        nearby = PriceReport.objects.create(
            user=self.user, product=self.product, business=self.second,
            price=Decimal('5.50'), currency='PGK',
            latitude=-6.729, longitude=146.995,
        )
        response = self.client.get(reverse('home'), {
            'sort': 'nearest', 'lat': '-6.73', 'lng': '146.99',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['location_fallback'])
        self.assertEqual(response.context['current_sort'], 'nearest')
        self.assertEqual([report.pk for report in response.context['latest_prices']], [nearby.pk])

    def test_invalid_coordinates_do_not_break_discovery(self):
        response = self.client.get(reverse('home'), {
            'sort': 'nearest', 'lat': '999', 'lng': '147.18',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_sort'], 'discover')

    def test_map_keeps_all_mappable_reports_even_if_feed_is_local(self):
        PriceReport.objects.create(
            user=self.user, product=self.product, business=self.busy,
            price=Decimal('6.50'), latitude=-9.443, longitude=147.18,
        )
        PriceReport.objects.create(
            user=self.user, product=self.product, business=self.third,
            price=Decimal('8.50'), latitude=-6.729, longitude=146.995,
        )
        response = self.client.get(reverse('api_map_prices'), {
            'sort': 'nearest', 'lat': '-6.73', 'lng': '146.99',
        })
        ids = {row['id'] for row in response.json()['items']}
        self.assertEqual(len(ids), 2)
