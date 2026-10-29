"""Stage 4: owned reports and product tracking regression tests."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Business, PriceReport, Product, ProductWatchlist


class PriceTrackingDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='tracker-owner', password='test-password')
        cls.other = User.objects.create_user(username='tracker-other', password='test-password')
        cls.product = Product.objects.create(name='Tracked Rice', slug='tracked-rice', created_by=cls.owner)
        cls.product2 = Product.objects.create(name='Tracked Milk', slug='tracked-milk', created_by=cls.owner)
        cls.store_a = Business.objects.create(name='Store A', slug='tracking-store-a')
        cls.store_b = Business.objects.create(name='Store B', slug='tracking-store-b')

    def setUp(self):
        self.client.force_login(self.owner)

    def make_report(self, product=None, business=None, price='10.00', user=None, currency='PGK', **kwargs):
        return PriceReport.objects.create(
            product=product or self.product,
            business=business if business is not None else self.store_a,
            user=user or self.other,
            price=Decimal(price),
            currency=currency,
            **kwargs,
        )

    def test_dashboard_has_report_and_tracked_tabs_even_with_no_contributions(self):
        ProductWatchlist.objects.create(user=self.owner, product=self.product)
        response = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_view'], 'tracked')
        self.assertEqual(response.context['tracked_count'], 1)
        self.assertContains(response, 'Tracked Rice')
        self.assertContains(response, 'No community prices reported')
        self.assertNotContains(response, 'No prices yet')

    def test_saved_products_are_private_to_authenticated_user(self):
        ProductWatchlist.objects.create(user=self.owner, product=self.product)
        ProductWatchlist.objects.create(user=self.other, product=self.product2)
        response = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        self.assertContains(response, 'Tracked Rice')
        self.assertNotContains(response, 'Tracked Milk')
        self.assertEqual(response.context['tracked_count'], 1)

    def test_latest_same_store_price_increase_is_reported(self):
        first = self.make_report(price='10.00')
        last = self.make_report(price='12.50')
        ProductWatchlist.objects.create(user=self.owner, product=self.product)
        response = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        tracked = response.context['tracked_page'].object_list[0]
        self.assertEqual(tracked.latest_report.pk, last.pk)
        self.assertEqual(tracked.previous_report.pk, first.pk)
        self.assertEqual(tracked.price_direction, 'up')
        self.assertEqual(tracked.price_delta, Decimal('2.50'))
        self.assertContains(response, 'Increased by PGK 2.50')
        self.assertContains(response, 'Previous same-shop report')

    def test_latest_different_store_is_not_a_false_price_drop(self):
        self.make_report(price='10.00', business=self.store_a)
        other_store = self.make_report(price='3.00', business=self.store_b)
        ProductWatchlist.objects.create(user=self.owner, product=self.product)
        response = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        tracked = response.context['tracked_page'].object_list[0]
        self.assertEqual(tracked.latest_report.pk, other_store.pk)
        self.assertIsNone(tracked.previous_report)
        self.assertNotContains(response, 'Decreased by')

    def test_downward_movement_shows_positive_amount(self):
        self.make_report(price='13.00')
        self.make_report(price='8.75')
        ProductWatchlist.objects.create(user=self.owner, product=self.product)
        response = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        tracked = response.context['tracked_page'].object_list[0]
        self.assertEqual(tracked.price_direction, 'down')
        self.assertEqual(tracked.price_drop_amount, Decimal('4.25'))
        self.assertContains(response, 'Decreased by PGK 4.25')

    def test_different_currency_and_flagged_reports_are_not_compared(self):
        self.make_report(price='5.00', currency='USD')
        last = self.make_report(price='12.00')
        self.make_report(price='1.00', marked_for_deletion=True)
        ProductWatchlist.objects.create(user=self.owner, product=self.product)
        response = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        tracked = response.context['tracked_page'].object_list[0]
        self.assertEqual(tracked.latest_report.pk, last.pk)
        self.assertIsNone(tracked.previous_report)
        self.assertIsNone(tracked.price_delta)

    def test_recent_contributions_only_show_owner_reports(self):
        own = self.make_report(price='17.00', user=self.owner)
        other = self.make_report(price='18.00', user=self.other)
        response = self.client.get(reverse('my_prices'))
        self.assertEqual(response.context['active_view'], 'reports')
        self.assertEqual([r.pk for r in response.context['recent_contributions']], [own.pk])
        self.assertNotIn(other.pk, [r.pk for r in response.context['recent_contributions']])
        self.assertContains(response, 'Your latest price reports')
        self.assertContains(response, '17.00')

    def test_tracked_products_paginate_at_twelve(self):
        for i in range(15):
            product = Product.objects.create(name=f'Watched {i}', slug=f'watched-{i}')
            ProductWatchlist.objects.create(user=self.owner, product=product)
        first = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        second = self.client.get(reverse('my_prices'), {'view': 'tracked', 'page': 2})
        self.assertEqual(len(first.context['tracked_page'].object_list), 12)
        self.assertEqual(len(second.context['tracked_page'].object_list), 3)
        self.assertContains(first, '?view=tracked&page=2')

    def test_product_page_has_track_action_and_html_toggle(self):
        url = reverse('product_detail', args=[self.product.pk])
        first = self.client.get(url)
        self.assertContains(first, 'Track this product')
        toggle = reverse('toggle_watchlist', args=[self.product.pk])
        result = self.client.post(toggle, {'return_to': 'product'})
        self.assertRedirects(result, url, fetch_redirect_response=False)
        self.assertTrue(ProductWatchlist.objects.filter(user=self.owner, product=self.product).exists())
        watched = self.client.get(url)
        self.assertContains(watched, 'Stop tracking')
        result = self.client.post(toggle, {'return_to': 'product'})
        self.assertRedirects(result, url, fetch_redirect_response=False)
        self.assertFalse(ProductWatchlist.objects.filter(user=self.owner, product=self.product).exists())

    def test_tracked_page_untrack_redirects_back_and_json_api_stays_unchanged(self):
        toggle = reverse('toggle_watchlist', args=[self.product.pk])
        json_added = self.client.post(toggle).json()
        self.assertEqual(json_added, {'watching': True})
        response = self.client.post(toggle, {'return_to': 'tracked'})
        self.assertRedirects(response, reverse('my_prices') + '?view=tracked', fetch_redirect_response=False)
        self.assertFalse(ProductWatchlist.objects.filter(user=self.owner, product=self.product).exists())

    def test_anonymous_user_cannot_access_personal_tracking(self):
        self.client.logout()
        response = self.client.get(reverse('my_prices'), {'view': 'tracked'})
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse('toggle_watchlist', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        product_page = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertContains(product_page, 'Sign in to track')
