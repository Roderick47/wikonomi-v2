from asgiref.sync import async_to_sync
from django.test import TestCase
from pydantic import ValidationError

from .legacy_tests import (
    MCPContributorToolTests,
    MCPOAuthConsentTests,
    MCPPermissionTests,
    MCPServiceTests,
    OpenAIPluginVerificationTests,
)
from .permissions import PUBLISH_SCOPE, READ_SCOPE, WRITE_SCOPE
from .server import mcp
from .tools import PriceObservation


class MCPToolSchemaTests(TestCase):
    def test_expected_safe_tool_surface_is_registered(self):
        tools = async_to_sync(mcp.list_tools)()
        names = {tool.name for tool in tools}

        self.assertEqual(names, {
            'get_schema_help',
            'search_wikonomi',
            'search_products',
            'get_product',
            'get_business',
            'get_branch',
            'compare_current_prices',
            'compare_product_value',
            'compare_basket',
            'list_shopping_lists',
            'get_shopping_list',
            'add_shopping_list_item',
            'update_shopping_list_item',
            'remove_shopping_list_item',
            'compare_shopping_list',
            'find_or_create_product',
            'submit_price',
            'bulk_submit_prices',
            'upload_evidence',
            'get_guide',
            'create_guide',
            'update_guide',
        })
        self.assertNotIn('delete_product', names)
        self.assertNotIn('merge_product', names)

    def test_annotations_distinguish_reads_private_writes_and_public_contributions(self):
        tools = {tool.name: tool for tool in async_to_sync(mcp.list_tools)()}
        read_names = {
            'get_schema_help',
            'search_wikonomi',
            'search_products',
            'get_product',
            'get_business',
            'get_branch',
            'get_guide',
            'compare_current_prices',
            'compare_product_value',
            'compare_basket',
            'list_shopping_lists',
            'get_shopping_list',
            'compare_shopping_list',
        }
        private_write_names = {
            'add_shopping_list_item',
            'update_shopping_list_item',
            'remove_shopping_list_item',
        }
        destructive_names = {'update_guide', 'remove_shopping_list_item'}

        for name, tool in tools.items():
            with self.subTest(tool=name):
                self.assertEqual(tool.annotations.read_only_hint, name in read_names)
                self.assertEqual(
                    tool.annotations.open_world_hint,
                    name not in read_names and name not in private_write_names,
                )
                self.assertEqual(tool.annotations.destructive_hint, name in destructive_names)
                self.assertNotIn('labels it AI-assisted', tool.description)

                expected_scopes = [READ_SCOPE]
                if name in {'create_guide', 'update_guide'}:
                    expected_scopes.append(PUBLISH_SCOPE)
                elif name not in read_names:
                    expected_scopes.append(WRITE_SCOPE)
                self.assertEqual(tool.meta['securitySchemes'], [
                    {'type': 'oauth2', 'scopes': expected_scopes},
                ])

    def test_price_tools_do_not_request_precise_user_location(self):
        schema = PriceObservation.model_json_schema()
        self.assertNotIn('latitude', schema['properties'])
        self.assertNotIn('longitude', schema['properties'])
        with self.assertRaises(ValidationError):
            PriceObservation(price='2.00', latitude=-9.47, longitude=147.2)
