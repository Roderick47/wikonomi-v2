from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from catalog.models import ProductIdentity
from catalog.value import build_basket_comparison, build_product_value_comparison
from core.models import Business, PriceReport, Product, ShoppingList, ShoppingListItem


class CurrentValuePriceSemanticsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='current-value-user', password='testpass123')
        self.store = Business.objects.create(name='Current Value Store', slug='current-value-store')
        self.product = Product.objects.create(
            name='Current Value Rice 1kg',
            slug='current-value-rice-1kg',
            created_by=self.user,
        )
        ProductIdentity.objects.update_or_create(
            product=self.product,
            defaults={
                'package_quantity': Decimal('1'),
                'package_unit': 'kg',
                'pack_count': 1,
                'source': ProductIdentity.Source.MANUAL,
            },
        )

        self.old_report = PriceReport.objects.create(
            product=self.product,
            business=self.store,
            user=self.user,
            price=Decimal('5.00'),
            currency='PGK',
        )
        PriceReport.objects.filter(pk=self.old_report.pk).update(
            observed_at=timezone.now() - timedelta(days=7)
        )
        self.old_report.refresh_from_db()

        self.new_report = PriceReport.objects.create(
            product=self.product,
            business=self.store,
            user=self.user,
            price=Decimal('10.00'),
            currency='PGK',
        )

    def test_product_value_uses_newer_store_price_not_historical_low(self):
        comparison = build_product_value_comparison(self.product, currency='PGK')

        exact_rows = [row for row in comparison['rows'] if row['product'].pk == self.product.pk]
        self.assertEqual(len(exact_rows), 1)
        self.assertEqual(exact_rows[0]['report'].pk, self.new_report.pk)
        self.assertEqual(exact_rows[0]['unit_price'], Decimal('10.00'))

    def test_basket_uses_newer_store_price_not_historical_low(self):
        shopping_list = ShoppingList.objects.create(user=self.user, name='Current basket')
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=self.product, quantity=2)

        comparison = build_basket_comparison(list(shopping_list.items.all()), currency='PGK')

        self.assertEqual(comparison['cheapest_full_store']['total'], Decimal('20.00'))
        self.assertEqual(comparison['split_total'], Decimal('20.00'))
        self.assertEqual(comparison['split_lines'][0]['report'].pk, self.new_report.pk)
