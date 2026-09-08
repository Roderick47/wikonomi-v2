from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductIdentity
from catalog.value import (
    build_basket_comparison,
    build_product_value_comparison,
    resolve_product_measure,
    unit_price_for_report,
)
from core.models import (
    Business,
    Category,
    PriceReport,
    Product,
    ShoppingList,
    ShoppingListItem,
)


class ValueComparisonTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='value-user', password='testpass123')
        self.category = Category.objects.create(name='Rice', slug='rice-value-test')
        self.store_a = Business.objects.create(name='Value Store A', slug='value-store-a')
        self.store_b = Business.objects.create(name='Value Store B', slug='value-store-b')

    def _product(self, name, *, brand='', quantity=None, unit='', pack_count=1):
        product = Product.objects.create(
            name=name,
            slug=name.lower().replace(' ', '-')[:50],
            category=self.category,
            created_by=self.user,
        )
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

    def _price(self, product, business, price, *, days_old=0):
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

    def test_unit_price_normalizes_mass(self):
        product = self._product(
            'Trukai Rice 500g',
            brand='Trukai',
            quantity=Decimal('500'),
            unit='g',
        )
        report = self._price(product, self.store_a, '6.00')

        unit_price = unit_price_for_report(report, resolve_product_measure(product))

        self.assertEqual(unit_price.label, 'kg')
        self.assertEqual(unit_price.amount, Decimal('12.00'))

    def test_unit_price_handles_multipack_volume(self):
        product = self._product(
            'Juice 6 x 250ml',
            quantity=Decimal('250'),
            unit='ml',
            pack_count=6,
        )
        report = self._price(product, self.store_a, '12.00')

        unit_price = unit_price_for_report(report, resolve_product_measure(product))

        self.assertEqual(unit_price.label, 'L')
        self.assertEqual(unit_price.amount, Decimal('8.00'))

    def test_value_ranking_compares_compatible_sizes_and_brands(self):
        one_kg = self._product(
            'Trukai Rice 1kg',
            brand='Trukai',
            quantity=Decimal('1'),
            unit='kg',
        )
        five_kg = self._product(
            'Trukai Rice 5kg',
            brand='Trukai',
            quantity=Decimal('5'),
            unit='kg',
        )
        alternative = self._product(
            'Roots Rice 5kg',
            brand='Roots',
            quantity=Decimal('5'),
            unit='kg',
        )
        self._price(one_kg, self.store_a, '10.00')
        self._price(five_kg, self.store_a, '45.00')
        self._price(alternative, self.store_b, '40.00')

        comparison = build_product_value_comparison(one_kg, currency='PGK')

        self.assertTrue(comparison['available'])
        self.assertEqual(comparison['best_value']['product'], alternative)
        self.assertEqual(comparison['best_value']['unit_price'], Decimal('8.00'))
        self.assertEqual(comparison['best_value']['relationship_key'], 'alternative')
        self.assertEqual(comparison['best_exact_product']['product'], one_kg)
        self.assertEqual(comparison['best_exact_product']['unit_price'], Decimal('10.00'))
        self.assertEqual(comparison['alternative_savings_amount'], Decimal('2.00'))
        self.assertEqual(comparison['alternative_savings_percent'], Decimal('20.0'))

    def test_stale_value_price_cannot_win(self):
        one_kg = self._product(
            'Trukai Rice 1kg',
            brand='Trukai',
            quantity=Decimal('1'),
            unit='kg',
        )
        five_kg = self._product(
            'Trukai Rice 5kg',
            brand='Trukai',
            quantity=Decimal('5'),
            unit='kg',
        )
        stale_alternative = self._product(
            'Roots Rice 5kg',
            brand='Roots',
            quantity=Decimal('5'),
            unit='kg',
        )
        self._price(one_kg, self.store_a, '10.00')
        self._price(five_kg, self.store_a, '45.00')
        self._price(stale_alternative, self.store_b, '30.00', days_old=120)

        comparison = build_product_value_comparison(one_kg, currency='PGK')

        self.assertEqual(comparison['best_value']['product'], five_kg)
        self.assertNotIn(
            stale_alternative.pk,
            [row['product'].pk for row in comparison['rows']],
        )

    def test_basket_compares_full_store_and_split_store_totals(self):
        rice = self._product(
            'Basket Rice 1kg',
            quantity=Decimal('1'),
            unit='kg',
        )
        flour = self._product(
            'Basket Flour 1kg',
            quantity=Decimal('1'),
            unit='kg',
        )
        self._price(rice, self.store_a, '10.00')
        self._price(rice, self.store_b, '8.00')
        self._price(flour, self.store_a, '20.00')
        self._price(flour, self.store_b, '25.00')

        shopping_list = ShoppingList.objects.create(user=self.user, name='Basket')
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=rice, quantity=1)
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=flour, quantity=2)

        comparison = build_basket_comparison(list(shopping_list.items.all()), currency='PGK')

        self.assertEqual(comparison['full_basket_store_count'], 2)
        self.assertEqual(comparison['cheapest_full_store']['store_name'], self.store_a.name)
        self.assertEqual(comparison['cheapest_full_store']['total'], Decimal('50.00'))
        self.assertTrue(comparison['split_complete'])
        self.assertEqual(comparison['split_total'], Decimal('48.00'))
        self.assertEqual(comparison['full_store_savings_amount'], Decimal('2.00'))
        self.assertEqual(comparison['full_store_savings_percent'], Decimal('4.00'))

    def test_basket_excludes_stale_prices_and_custom_items(self):
        rice = self._product(
            'Current Rice 1kg',
            quantity=Decimal('1'),
            unit='kg',
        )
        flour = self._product(
            'Missing Flour 1kg',
            quantity=Decimal('1'),
            unit='kg',
        )
        self._price(rice, self.store_a, '10.00')
        self._price(flour, self.store_a, '20.00', days_old=120)

        shopping_list = ShoppingList.objects.create(user=self.user, name='Basket with gaps')
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=rice)
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=flour)
        ShoppingListItem.objects.create(shopping_list=shopping_list, item_name='Fresh vegetables')

        comparison = build_basket_comparison(list(shopping_list.items.all()), currency='PGK')

        self.assertFalse(comparison['split_complete'])
        self.assertEqual(comparison['custom_item_count'], 1)
        self.assertEqual([product.pk for product in comparison['missing_products']], [flour.pk])
        self.assertEqual(comparison['best_coverage_store']['coverage_count'], 1)
        self.assertEqual(comparison['best_coverage_store']['coverage_total'], 2)

    def test_value_and_basket_pages_render(self):
        product = self._product(
            'Page Rice 1kg',
            quantity=Decimal('1'),
            unit='kg',
        )
        self._price(product, self.store_a, '10.00')

        response = self.client.get(reverse('product_value_analysis', args=[product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unit value comparison')

        shopping_list = ShoppingList.objects.create(user=self.user, name='Page basket')
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=product)
        self.client.login(username='value-user', password='testpass123')
        response = self.client.get(reverse('shopping_list_compare'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Basket comparison')
