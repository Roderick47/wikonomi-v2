from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from comments.models import Comment
from core.models import (
    Business,
    BusinessInventoryItem,
    Notification,
    PriceReport,
    Product,
    ProductAlias,
    ProductWatchlist,
    ShoppingList,
    ShoppingListItem,
)

from .merge import merge_products
from .services import ensure_product_identity


class ProductMergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='merge-tester', password='testpass')
        self.business = Business.objects.create(name='Merge Mart', slug='merge-mart')

    def make_product(self, name, slug, barcode=''):
        product = Product.objects.create(name=name, slug=slug, created_by=self.user)
        ensure_product_identity(product, barcode=barcode)
        return product

    def test_merge_preserves_and_coalesces_related_product_data(self):
        target = self.make_product('Maxicorn 140grams', 'maxicorn-140grams')
        source = self.make_product('Maxicorn Snack 140grams', 'maxicorn-snack-140grams')
        ProductAlias.objects.create(canonical_product=source, alias_name='Maxicorn Snack 140g')

        PriceReport.objects.create(
            product=target,
            business=self.business,
            user=self.user,
            price=Decimal('7.50'),
        )
        PriceReport.objects.create(
            product=source,
            business=self.business,
            user=self.user,
            price=Decimal('7.00'),
        )

        BusinessInventoryItem.objects.create(
            business=self.business,
            product=target,
            description='',
        )
        BusinessInventoryItem.objects.create(
            business=self.business,
            product=source,
            sku='MAX-140',
            barcode='9300123456789',
            brand='Maxicorn',
            unit='140g',
            stock_quantity=Decimal('12'),
        )

        ProductWatchlist.objects.create(user=self.user, product=target)
        ProductWatchlist.objects.create(user=self.user, product=source)
        shopping_list = ShoppingList.objects.create(user=self.user, name='Groceries')
        shopping_item = ShoppingListItem.objects.create(
            shopping_list=shopping_list,
            product=source,
            item_name=source.name,
        )
        notification = Notification.objects.create(
            user=self.user,
            product=source,
            message='Test product notification',
        )
        product_type = ContentType.objects.get_for_model(Product)
        comment = Comment.objects.create(
            user=self.user,
            content_type=product_type,
            object_id=source.pk,
            body='Same product under another name.',
        )

        result = merge_products(source, target, reviewed_by=self.user)

        self.assertEqual(result['target_id'], target.pk)
        self.assertFalse(Product.objects.filter(pk=source.pk).exists())
        self.assertEqual(PriceReport.objects.filter(product=target).count(), 2)
        self.assertEqual(ProductWatchlist.objects.filter(user=self.user, product=target).count(), 1)

        inventory = BusinessInventoryItem.objects.get(business=self.business, product=target)
        self.assertEqual(inventory.sku, 'MAX-140')
        self.assertEqual(inventory.barcode, '9300123456789')
        self.assertEqual(inventory.brand, 'Maxicorn')

        shopping_item.refresh_from_db()
        notification.refresh_from_db()
        comment.refresh_from_db()
        self.assertEqual(shopping_item.product_id, target.pk)
        self.assertEqual(notification.product_id, target.pk)
        self.assertEqual(comment.object_id, target.pk)
        self.assertTrue(ProductAlias.objects.filter(
            canonical_product=target,
            alias_name='Maxicorn Snack 140grams',
        ).exists())
        self.assertTrue(ProductAlias.objects.filter(
            canonical_product=target,
            alias_name='Maxicorn Snack 140g',
        ).exists())

    def test_merge_blocks_conflicting_barcodes(self):
        target = self.make_product('Besta Tuna 185g', 'besta-tuna-185g', barcode='1111111111111')
        source = self.make_product('Besta Tuna Can 185g', 'besta-tuna-can-185g', barcode='2222222222222')

        with self.assertRaisesMessage(ValueError, 'conflicting barcodes'):
            merge_products(source, target, reviewed_by=self.user)

        self.assertTrue(Product.objects.filter(pk=source.pk).exists())

    def test_merge_blocks_different_package_sizes(self):
        target = self.make_product('Trukai Rice 1kg', 'trukai-rice-1kg')
        source = self.make_product('Trukai Rice 5kg', 'trukai-rice-5kg')

        with self.assertRaisesMessage(ValueError, 'different structured package sizes'):
            merge_products(source, target, reviewed_by=self.user)

        self.assertTrue(Product.objects.filter(pk=source.pk).exists())
