from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import ProductIdentity
from core.models import Business, PriceReport, Product

from .smart_search_services import search_products
from .smart_search_wrapper import search_wikonomi


@override_settings(WIKONOMI_MCP_PUBLIC_BASE_URL='https://www.wikonomi.com')
class MCPSmartSearchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='smart-search-user')
        self.store_a = Business.objects.create(name='Store A', slug='smart-store-a')
        self.store_b = Business.objects.create(name='Store B', slug='smart-store-b')

    def _product(self, name, *, brand='', quantity=None, unit='', pack_count=1, barcode=''):
        product = Product.objects.create(
            name=name,
            slug=f'smart-{Product.objects.count() + 1}',
            created_by=self.user,
        )
        ProductIdentity.objects.update_or_create(
            product=product,
            defaults={
                'brand': brand,
                'package_quantity': quantity,
                'package_unit': unit,
                'pack_count': pack_count,
                'barcode': barcode,
                'normalized_barcode': barcode.replace('-', '').replace(' ', '').casefold(),
                'source': ProductIdentity.Source.MANUAL,
                'confidence': Decimal('1.000'),
            },
        )
        return product

    def _price(self, product, business, price, *, age_days=0):
        report = PriceReport.objects.create(
            product=product,
            business=business,
            price=Decimal(str(price)),
            currency='PGK',
            user=self.user,
        )
        if age_days:
            observed_at = timezone.now() - timedelta(days=age_days)
            PriceReport.objects.filter(pk=report.pk).update(observed_at=observed_at)
            report.observed_at = observed_at
        return report

    def test_barcode_filter_returns_exact_product_even_when_text_does_not_match(self):
        product = self._product(
            'Ox & Palm Corned Beef 340g',
            brand='Ox & Palm',
            quantity=Decimal('340'),
            unit='g',
            barcode='9401234567890',
        )

        payload = search_products('scan this item', barcode='9401234567890')

        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['id'], product.pk)
        self.assertEqual(payload['results'][0]['match']['basis'], 'barcode')
        self.assertEqual(payload['results'][0]['match']['relationship'], 'exact_product')
        self.assertEqual(payload['interpreted_query']['barcode'], '9401234567890')

    def test_cheap_pack_size_query_prefers_lower_fresh_current_price(self):
        trukai = self._product('Trukai Rice 1kg', brand='Trukai', quantity=Decimal('1'), unit='kg')
        roots = self._product('Roots Rice 1kg', brand='Roots', quantity=Decimal('1'), unit='kg')
        self._price(trukai, self.store_a, '10.00')
        self._price(roots, self.store_b, '8.00')

        payload = search_products('cheap 1kg rice')

        self.assertTrue(payload['intent']['cheapest'])
        self.assertEqual(payload['interpreted_query']['package_quantity'], '1')
        self.assertEqual(payload['interpreted_query']['package_unit'], 'kg')
        self.assertEqual(payload['results'][0]['id'], roots.pk)
        self.assertEqual(payload['results'][0]['current_price_summary']['min_price'], '8.00')
        self.assertEqual(payload['results'][1]['id'], trukai.pk)

    def test_generic_search_keeps_smart_product_ranking(self):
        expensive = self._product('Alpha Rice 1kg', brand='Alpha', quantity=Decimal('1'), unit='kg')
        cheap = self._product('Zulu Rice 1kg', brand='Zulu', quantity=Decimal('1'), unit='kg')
        self._price(expensive, self.store_a, '12.00')
        self._price(cheap, self.store_b, '7.00')

        payload = search_wikonomi('cheapest 1kg rice', ['product'], 10)

        self.assertEqual(payload['results'][0]['id'], cheap.pk)
        self.assertEqual(payload['results'][1]['id'], expensive.pk)

    def test_current_only_excludes_products_whose_latest_price_is_stale(self):
        stale = self._product('Old Rice 1kg', brand='Old', quantity=Decimal('1'), unit='kg')
        self._price(stale, self.store_a, '5.00', age_days=120)

        all_results = search_products('rice')
        current_results = search_products('rice', current_only=True)

        self.assertEqual(all_results['count'], 1)
        self.assertEqual(all_results['results'][0]['current_price_summary']['comparable_store_count'], 0)
        self.assertEqual(all_results['results'][0]['current_price_summary']['stale_excluded_count'], 1)
        self.assertEqual(current_results['results'], [])

    def test_specific_brand_can_suppress_competitor_alternatives(self):
        trukai = self._product('Trukai Rice 1kg', brand='Trukai', quantity=Decimal('1'), unit='kg')
        roots = self._product('Roots Rice 1kg', brand='Roots', quantity=Decimal('1'), unit='kg')
        self._price(trukai, self.store_a, '10.00')
        self._price(roots, self.store_b, '8.00')

        payload = search_products('rice', brand='Trukai', include_alternatives=False)

        self.assertEqual([row['id'] for row in payload['results']], [trukai.pk])
        self.assertEqual(payload['results'][0]['match']['relationship'], 'exact_product')

    def test_inferred_brand_labels_other_brand_as_comparable_alternative(self):
        trukai = self._product('Trukai Rice 1kg', brand='Trukai', quantity=Decimal('1'), unit='kg')
        roots = self._product('Roots Rice 1kg', brand='Roots', quantity=Decimal('1'), unit='kg')
        self._price(trukai, self.store_a, '10.00')
        self._price(roots, self.store_b, '8.00')

        payload = search_products('Trukai rice 1kg')
        rows = {row['id']: row for row in payload['results']}

        self.assertEqual(payload['interpreted_query']['brand'], 'Trukai')
        self.assertEqual(rows[trukai.pk]['match']['relationship'], 'exact_product')
        self.assertEqual(rows[roots.pk]['match']['relationship'], 'comparable_alternative')
