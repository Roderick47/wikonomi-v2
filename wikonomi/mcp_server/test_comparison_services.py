from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from catalog.models import ProductIdentity
from core.models import Business, PriceReport, Product
from mcp_server.comparison_services import (
    compare_basket,
    compare_current_prices,
    compare_product_value,
)


class MCPComparisonServicesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mcp-comparison-user')
        self.store_a = Business.objects.create(name='Comparison Store A', slug='comparison-store-a')
        self.store_b = Business.objects.create(name='Comparison Store B', slug='comparison-store-b')

    def _product(self, name, brand='', quantity=None, unit='', pack_count=1):
        product = Product.objects.create(name=name, slug=f'comparison-{Product.objects.count() + 1}', created_by=self.user)
        ProductIdentity.objects.update_or_create(
            product=product,
            defaults={
                'brand': brand,
                'package_quantity': quantity,
                'package_unit': unit,
                'pack_count': pack_count,
                'source': ProductIdentity.Source.MANUAL,
            },
        )
        return product

    def _price(self, product, business, price, days_old=0):
        report = PriceReport.objects.create(
            product=product,
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

    def test_current_comparison_uses_latest_store_observation(self):
        rice = self._product('Current MCP Rice 1kg', quantity=Decimal('1'), unit='kg')
        self._price(rice, self.store_a, '5.00', days_old=20)
        self._price(rice, self.store_a, '10.00')
        winner = self._price(rice, self.store_b, '8.00')

        result = compare_current_prices(rice.pk)

        self.assertEqual(result['best_price']['id'], winner.pk)
        self.assertEqual(result['potential_savings']['amount'], '2.00')
        self.assertEqual(result['comparable_store_count'], 2)

    def test_stale_price_cannot_win_current_comparison(self):
        rice = self._product('Stale MCP Rice 1kg', quantity=Decimal('1'), unit='kg')
        stale = self._price(rice, self.store_a, '4.00', days_old=120)
        fresh = self._price(rice, self.store_b, '9.00')

        result = compare_current_prices(rice.pk)

        self.assertEqual(result['best_price']['id'], fresh.pk)
        self.assertEqual(result['stale_excluded_count'], 1)
        stale_row = next(row for row in result['prices'] if row['id'] == stale.pk)
        self.assertEqual(stale_row['freshness'], 'stale')

    def test_unit_value_comparison_exposes_alternative_without_calling_it_exact(self):
        one_kg = self._product('Value MCP Rice 1kg', brand='Trukai', quantity=Decimal('1'), unit='kg')
        five_kg = self._product('Value MCP Rice 5kg', brand='Trukai', quantity=Decimal('5'), unit='kg')
        alternative = self._product('Value MCP Rice 5kg Alternative', brand='Roots', quantity=Decimal('5'), unit='kg')
        # Keep the same normalized base name for the cross-brand alternative.
        alternative.name = 'Value MCP Rice 5kg'
        alternative.save(update_fields=['name'])
        self._price(one_kg, self.store_a, '10.00')
        self._price(five_kg, self.store_a, '45.00')
        self._price(alternative, self.store_b, '40.00')

        result = compare_product_value(one_kg.pk)

        self.assertTrue(result['available'])
        self.assertEqual(result['best_value']['unit_price'], '8.00')
        self.assertEqual(result['best_value']['relationship_key'], 'alternative')
        self.assertEqual(result['best_exact_product']['relationship_key'], 'exact')

    def test_basket_compares_exact_products_and_reports_split_saving(self):
        rice = self._product('Basket MCP Rice 1kg', quantity=Decimal('1'), unit='kg')
        flour = self._product('Basket MCP Flour 1kg', quantity=Decimal('1'), unit='kg')
        self._price(rice, self.store_a, '10.00')
        self._price(rice, self.store_b, '8.00')
        self._price(flour, self.store_a, '20.00')
        self._price(flour, self.store_b, '25.00')

        result = compare_basket([
            {'product_id': rice.pk, 'quantity': 1},
            {'product_id': flour.pk, 'quantity': 2},
        ])

        self.assertEqual(result['cheapest_full_store']['store_name'], self.store_a.name)
        self.assertEqual(result['cheapest_full_store']['total'], '50.00')
        self.assertTrue(result['split_store']['complete'])
        self.assertEqual(result['split_store']['total'], '48.00')
        self.assertEqual(result['split_store']['saving_vs_cheapest_complete_store']['amount'], '2.00')
        self.assertEqual(result['missing_current_price_products'], [])

    def test_basket_surfaces_missing_current_price_instead_of_substituting(self):
        rice = self._product('Covered MCP Rice 1kg', quantity=Decimal('1'), unit='kg')
        flour = self._product('Uncovered MCP Flour 1kg', quantity=Decimal('1'), unit='kg')
        self._price(rice, self.store_a, '10.00')
        self._price(flour, self.store_a, '20.00', days_old=120)

        result = compare_basket([
            {'product_id': rice.pk, 'quantity': 1},
            {'product_id': flour.pk, 'quantity': 1},
        ])

        self.assertFalse(result['split_store']['complete'])
        self.assertEqual(result['missing_current_price_products'], [{'id': flour.pk, 'name': flour.name}])
        self.assertFalse(result['best_coverage_store']['is_full_basket'])
