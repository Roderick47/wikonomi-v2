from datetime import timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch

from core.models import Business, BusinessBranch, BusinessInventoryItem, PriceReport, Product

from .business_intelligence_services import get_branch, get_business
from .business_search_policy import search_businesses
from .models import MCPUserAccess
from .permissions import ALL_SCOPES, build_actor
from .server import mcp


@override_settings(WIKONOMI_MCP_PUBLIC_BASE_URL='https://www.wikonomi.com')
class MCPBusinessIntelligenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='business-intel-user')
        self.business = Business.objects.create(name='RH Test', slug='rh-test')
        self.vision = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Vision City',
            slug='vision-city',
            address='Waigani Drive, Port Moresby',
            latitude=-9.4438,
            longitude=147.1803,
            phone='70000001',
            email='vision@example.com',
            is_main_branch=True,
        )
        self.boroko = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Boroko',
            slug='boroko',
            address='Boroko, Port Moresby',
        )
        self.rice = Product.objects.create(name='Test Rice 1kg', slug='test-rice-1kg')
        self.oil = Product.objects.create(name='Test Oil 1L', slug='test-oil-1l')
        self.actor = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='business-intel-test')

    def add_price(self, product, branch, price, *, days=1, currency='PGK', business=None):
        business = business or branch.canonical_business
        report = PriceReport.objects.create(
            product=product,
            business=business,
            business_branch=branch,
            price=Decimal(str(price)),
            currency=currency,
            user=self.user,
        )
        observed_at = timezone.now() - timedelta(days=days)
        PriceReport.objects.filter(pk=report.pk).update(observed_at=observed_at)
        report.refresh_from_db()
        return report

    def test_branch_returns_latest_price_per_product_and_excludes_stale_by_default(self):
        self.add_price(self.rice, self.vision, '5.00', days=20)
        self.add_price(self.rice, self.vision, '8.00', days=1)
        self.add_price(self.oil, self.vision, '12.00', days=120)

        result = get_branch(self.vision.pk)

        self.assertEqual(result['id'], self.vision.pk)
        self.assertEqual(result['address'], 'Waigani Drive, Port Moresby')
        self.assertEqual(len(result['prices']), 1)
        self.assertEqual(result['prices'][0]['product_id'], self.rice.pk)
        self.assertEqual(result['prices'][0]['price'], '8.00')
        self.assertEqual(result['price_coverage']['current_product_count'], 1)
        self.assertEqual(result['price_coverage']['stale_only_product_count'], 1)

    def test_branch_can_show_stale_context_without_calling_it_current(self):
        self.add_price(self.oil, self.vision, '12.00', days=120)
        result = get_branch(self.vision.pk, include_stale=True)
        self.assertEqual(result['prices'][0]['freshness'], 'stale')
        self.assertEqual(result['price_coverage']['current_product_count'], 0)

    def test_business_groups_current_products_across_branches(self):
        self.add_price(self.rice, self.vision, '8.00', days=2)
        self.add_price(self.rice, self.boroko, '7.50', days=1)
        self.add_price(self.oil, self.vision, '11.00', days=130)

        result = get_business(self.business.pk, include_inventory=False)

        self.assertEqual(result['price_coverage']['current_product_count'], 1)
        self.assertEqual(result['price_coverage']['stale_only_product_count'], 1)
        self.assertEqual(len(result['current_products']), 1)
        rice = result['current_products'][0]
        self.assertEqual(rice['product_id'], self.rice.pk)
        self.assertEqual(rice['location_count'], 2)
        self.assertEqual(rice['min_price'], '7.50')
        self.assertEqual(rice['best_price']['branch_id'], self.boroko.pk)

    def test_business_inventory_is_explicitly_business_wide_not_branch_specific(self):
        BusinessInventoryItem.objects.create(
            business=self.business,
            product=self.oil,
            sku='OIL-1L',
            barcode='9400000000001',
            brand='Test Brand',
            unit='1L',
            stock_quantity=Decimal('12'),
        )

        business_result = get_business(self.business.pk)
        branch_result = get_branch(self.vision.pk)

        self.assertEqual(business_result['business_inventory']['item_count'], 1)
        self.assertFalse(business_result['business_inventory']['branch_specific'])
        self.assertFalse(branch_result['business_inventory']['branch_specific'])
        self.assertEqual(branch_result['business_inventory']['item_count'], 1)
        self.assertEqual(branch_result['prices'], [])

    def test_business_search_returns_matching_branch_id_and_current_coverage(self):
        self.add_price(self.rice, self.vision, '8.00', days=1)
        results = search_businesses('Vision City')

        self.assertEqual(results[0]['id'], self.business.pk)
        self.assertEqual(results[0]['matching_branches'][0]['id'], self.vision.pk)
        self.assertEqual(results[0]['price_coverage']['current_product_count'], 1)

    def test_business_search_can_discover_business_and_branch_from_current_product_data(self):
        self.add_price(self.rice, self.vision, '8.00', days=1)
        results = search_businesses('Rice')

        self.assertEqual(results[0]['id'], self.business.pk)
        self.assertEqual(results[0]['matching_current_product_count'], 1)
        self.assertEqual(results[0]['matching_current_products'][0]['product_id'], self.rice.pk)
        self.assertEqual(results[0]['matching_branches'][0]['id'], self.vision.pk)

    def test_stale_product_data_is_searchable_but_not_labelled_current(self):
        stale_business = Business.objects.create(name='Old Price Mart', slug='old-price-mart')
        stale_branch = BusinessBranch.objects.create(
            canonical_business=stale_business,
            name='Old Branch',
            slug='old-branch',
        )
        self.add_price(self.rice, stale_branch, '5.00', days=150, business=stale_business)

        result = search_businesses('Rice')[0]
        self.assertEqual(result['id'], stale_business.pk)
        self.assertEqual(result['matching_current_product_count'], 0)
        self.assertEqual(result['price_coverage']['stale_only_product_count'], 1)

    def test_business_inventory_can_make_business_discoverable_without_claiming_current_price(self):
        BusinessInventoryItem.objects.create(
            business=self.business,
            product=self.oil,
            sku='OIL-CATALOG',
            brand='Catalog Brand',
            barcode='9400000000999',
        )
        result = search_businesses('Catalog Brand')[0]
        self.assertEqual(result['id'], self.business.pk)
        self.assertEqual(result['matching_current_product_count'], 0)
        self.assertEqual(result['matching_inventory_products'][0]['scope'], 'business_wide')

    def test_business_product_query_narrows_current_products(self):
        self.add_price(self.rice, self.vision, '8.00', days=1)
        self.add_price(self.oil, self.vision, '11.00', days=1)
        result = get_business(self.business.pk, product_query='Rice', include_inventory=False)
        self.assertEqual([item['product_id'] for item in result['current_products']], [self.rice.pk])


class MCPBusinessToolDispatchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='business-tool-user')
        self.actor = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='business-tool-test')
        self.business = Business.objects.create(name='Dispatch Mart', slug='dispatch-mart')
        self.branch = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Town Branch',
            slug='town-branch',
        )

    def test_get_business_and_get_branch_dispatch_through_mcp(self):
        with patch('mcp_server.services.current_actor', return_value=self.actor):
            business_result = async_to_sync(mcp.call_tool)('get_business', {'business_id': self.business.pk})
            branch_result = async_to_sync(mcp.call_tool)('get_branch', {'branch_id': self.branch.pk})

        self.assertFalse(business_result.is_error)
        self.assertFalse(branch_result.is_error)
        self.assertEqual(business_result.structured_content['id'], self.business.pk)
        self.assertEqual(branch_result.structured_content['id'], self.branch.pk)

    def test_read_tools_are_available_to_explicit_reader(self):
        MCPUserAccess.objects.create(user=self.user, role=MCPUserAccess.Role.READER)
        reader = build_actor(user=self.user, token_scopes=ALL_SCOPES, client_id='reader-client')
        with patch('mcp_server.services.current_actor', return_value=reader):
            result = async_to_sync(mcp.call_tool)('get_branch', {'branch_id': self.branch.pk})
        self.assertFalse(result.is_error)
