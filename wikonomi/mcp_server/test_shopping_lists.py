from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Business, PriceReport, Product, ShoppingList, ShoppingListItem

from .models import MCPAuditLog, MCPUserAccess
from .permissions import ALL_SCOPES, READ_SCOPE, build_actor
from .server import mcp
from .shopping_list_services import (
    add_shopping_list_item,
    compare_shopping_list,
    get_shopping_list,
    list_shopping_lists,
    remove_shopping_list_item,
    update_shopping_list_item,
)


@override_settings(WIKONOMI_MCP_PUBLIC_BASE_URL='https://www.wikonomi.com')
class MCPShoppingListServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='shopper')
        self.other = User.objects.create_user(username='other-shopper')
        self.actor = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='shopping-test')
        self.rice = Product.objects.create(name='Shopping Test Rice 1kg', slug='shopping-test-rice-1kg')
        self.oil = Product.objects.create(name='Shopping Test Oil 1L', slug='shopping-test-oil-1l')

    def add_price(self, product, business, price, *, days=1):
        report = PriceReport.objects.create(
            product=product,
            business=business,
            price=Decimal(str(price)),
            currency='PGK',
            user=self.user,
        )
        PriceReport.objects.filter(pk=report.pk).update(observed_at=timezone.now() - timedelta(days=days))
        report.refresh_from_db()
        return report

    def test_list_and_get_only_return_authenticated_users_lists(self):
        own = ShoppingList.objects.create(user=self.user, name='Own List')
        ShoppingListItem.objects.create(shopping_list=own, product=self.rice, item_name=self.rice.name)
        foreign = ShoppingList.objects.create(user=self.other, name='Foreign List')
        ShoppingListItem.objects.create(shopping_list=foreign, product=self.oil, item_name=self.oil.name)

        listed = list_shopping_lists(self.actor)
        self.assertEqual(listed['count'], 1)
        self.assertEqual(listed['shopping_lists'][0]['id'], own.pk)

        fetched = get_shopping_list(self.actor, own.pk)
        self.assertEqual([item['product_id'] for item in fetched['items']], [self.rice.pk])
        with self.assertRaisesMessage(ValueError, 'was not found for the authenticated user'):
            get_shopping_list(self.actor, foreign.pk)

    def test_multiple_lists_require_explicit_selection(self):
        ShoppingList.objects.create(user=self.user, name='List A')
        ShoppingList.objects.create(user=self.user, name='List B')
        with self.assertRaisesMessage(ValueError, 'Multiple shopping lists exist'):
            get_shopping_list(self.actor)
        with self.assertRaisesMessage(ValueError, 'Multiple shopping lists exist'):
            add_shopping_list_item(self.actor, self.rice.pk)
        with self.assertRaisesMessage(ValueError, 'Multiple shopping lists exist'):
            compare_shopping_list(self.actor)

    def test_add_creates_default_list_then_increments_existing_product(self):
        first = add_shopping_list_item(self.actor, self.rice.pk, quantity=2)
        self.assertTrue(first['list_created'])
        self.assertEqual(first['action'], 'created')
        item_id = first['item']['id']

        item = ShoppingListItem.objects.get(pk=item_id)
        item.is_checked = True
        item.save(update_fields=['is_checked'])

        second = add_shopping_list_item(
            self.actor,
            self.rice.pk,
            shopping_list_id=first['shopping_list']['id'],
            quantity=3,
        )
        item.refresh_from_db()
        self.assertEqual(second['action'], 'quantity_increased')
        self.assertEqual(second['previous_quantity'], 2)
        self.assertEqual(item.quantity, 5)
        self.assertFalse(item.is_checked)
        self.assertEqual(ShoppingListItem.objects.filter(shopping_list_id=item.shopping_list_id, product=self.rice).count(), 1)

    def test_update_sets_absolute_quantity_and_checked_state(self):
        shopping_list = ShoppingList.objects.create(user=self.user, name='Weekly')
        item = ShoppingListItem.objects.create(
            shopping_list=shopping_list,
            product=self.rice,
            item_name=self.rice.name,
            quantity=2,
        )
        result = update_shopping_list_item(self.actor, item.pk, quantity=7, is_checked=True)
        item.refresh_from_db()
        self.assertEqual(result['action'], 'updated')
        self.assertEqual(item.quantity, 7)
        self.assertTrue(item.is_checked)

    def test_remove_is_owner_scoped_and_repeated_remove_is_safe(self):
        own_list = ShoppingList.objects.create(user=self.user, name='Own')
        own_item = ShoppingListItem.objects.create(shopping_list=own_list, product=self.rice, item_name=self.rice.name)
        foreign_list = ShoppingList.objects.create(user=self.other, name='Foreign')
        foreign_item = ShoppingListItem.objects.create(shopping_list=foreign_list, product=self.oil, item_name=self.oil.name)

        removed = remove_shopping_list_item(self.actor, own_item.pk)
        self.assertTrue(removed['removed'])
        again = remove_shopping_list_item(self.actor, own_item.pk)
        self.assertFalse(again['removed'])

        foreign_attempt = remove_shopping_list_item(self.actor, foreign_item.pk)
        self.assertFalse(foreign_attempt['removed'])
        self.assertTrue(ShoppingListItem.objects.filter(pk=foreign_item.pk).exists())

    def test_compare_saved_list_uses_fresh_exact_products_and_surfaces_unresolved_items(self):
        shopping_list = ShoppingList.objects.create(user=self.user, name='Groceries')
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=self.rice, item_name=self.rice.name, quantity=2)
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=self.oil, item_name=self.oil.name, quantity=1, is_checked=True)
        ShoppingListItem.objects.create(shopping_list=shopping_list, item_name='Fresh kaukau', quantity=4)

        store_a = Business.objects.create(name='Shopping Store A', slug='shopping-store-a')
        store_b = Business.objects.create(name='Shopping Store B', slug='shopping-store-b')
        self.add_price(self.rice, store_a, '10.00', days=2)
        self.add_price(self.rice, store_b, '8.00', days=1)
        self.add_price(self.oil, store_a, '2.00', days=1)

        result = compare_shopping_list(self.actor, shopping_list.pk)
        self.assertEqual(result['product_item_count'], 1)
        self.assertEqual(result['checked_item_count_excluded'], 1)
        self.assertEqual(len(result['unresolved_custom_items']), 1)
        self.assertEqual(result['unresolved_custom_items'][0]['item_name'], 'Fresh kaukau')
        self.assertEqual(result['split_store']['total'], '16.00')
        self.assertEqual(result['split_store']['items'][0]['product_id'], self.rice.pk)
        self.assertEqual(result['split_store']['items'][0]['business_id'], store_b.pk)

    def test_stale_saved_product_is_reported_missing_not_substituted(self):
        shopping_list = ShoppingList.objects.create(user=self.user, name='Stale Basket')
        ShoppingListItem.objects.create(shopping_list=shopping_list, product=self.rice, item_name=self.rice.name)
        store = Business.objects.create(name='Stale Shopping Store', slug='stale-shopping-store')
        self.add_price(self.rice, store, '4.00', days=120)

        result = compare_shopping_list(self.actor, shopping_list.pk)
        self.assertFalse(result['split_store']['complete'])
        self.assertEqual(result['split_store']['total'], None)
        self.assertEqual(result['missing_current_price_products'], [{'id': self.rice.pk, 'name': self.rice.name}])


class MCPShoppingListToolTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='shopping-tool-user')
        self.product = Product.objects.create(name='MCP Shopping Tool Rice', slug='mcp-shopping-tool-rice')
        self.actor = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='shopping-tool-client')

    def test_add_idempotency_key_prevents_sequential_retry_increment(self):
        arguments = {
            'product_id': self.product.pk,
            'quantity': 1,
            'idempotency_key': 'retry-safe-add-1',
        }
        with patch('mcp_server.services.current_actor', return_value=self.actor):
            first = async_to_sync(mcp.call_tool)('add_shopping_list_item', arguments)
            second = async_to_sync(mcp.call_tool)('add_shopping_list_item', arguments)

        self.assertFalse(first.is_error)
        self.assertFalse(second.is_error)
        item = ShoppingListItem.objects.get(product=self.product, shopping_list__user=self.user)
        self.assertEqual(item.quantity, 1)
        self.assertTrue(second.structured_content['idempotent_replay'])
        self.assertEqual(
            MCPAuditLog.objects.filter(tool_name='add_shopping_list_item', status=MCPAuditLog.Status.SUCCEEDED).count(),
            2,
        )

    def test_reader_can_read_and_compare_but_cannot_write(self):
        shopping_list = ShoppingList.objects.create(user=self.user, name='Reader List')
        MCPUserAccess.objects.create(user=self.user, role=MCPUserAccess.Role.READER)
        reader = build_actor(user=self.user, token_scopes=[READ_SCOPE], client_id='reader-client')

        with patch('mcp_server.services.current_actor', return_value=reader):
            listed = async_to_sync(mcp.call_tool)('list_shopping_lists', {})
            fetched = async_to_sync(mcp.call_tool)('get_shopping_list', {'shopping_list_id': shopping_list.pk})
            compared = async_to_sync(mcp.call_tool)('compare_shopping_list', {'shopping_list_id': shopping_list.pk})
            denied = async_to_sync(mcp.call_tool)(
                'add_shopping_list_item',
                {'shopping_list_id': shopping_list.pk, 'product_id': self.product.pk},
            )

        self.assertFalse(listed.is_error)
        self.assertFalse(fetched.is_error)
        self.assertFalse(compared.is_error)
        self.assertTrue(denied.is_error)
