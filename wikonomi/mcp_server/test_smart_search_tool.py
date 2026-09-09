from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import ProductIdentity
from core.models import Product

from .permissions import READ_SCOPE, build_actor
from .server import mcp


@override_settings(WIKONOMI_MCP_PUBLIC_BASE_URL='https://www.wikonomi.com')
class MCPSmartSearchToolTests(TestCase):
    def test_reader_can_call_structured_search_tool_without_write_scope(self):
        user = get_user_model().objects.create_user(username='smart-search-reader')
        actor = build_actor(user=user, token_scopes=[READ_SCOPE], client_id='smart-search-test')
        product = Product.objects.create(name='Trukai Rice 1kg', slug='tool-trukai-rice')
        ProductIdentity.objects.update_or_create(
            product=product,
            defaults={
                'brand': 'Trukai',
                'package_quantity': '1.000',
                'package_unit': 'kg',
                'pack_count': 1,
                'source': ProductIdentity.Source.MANUAL,
            },
        )

        with patch('mcp_server.services.current_actor', return_value=actor):
            result = async_to_sync(mcp.call_tool)('search_products', {
                'query': 'Trukai rice 1kg',
                'brand': 'Trukai',
                'package_quantity': '1',
                'package_unit': 'kg',
                'include_alternatives': False,
            })

        self.assertFalse(result.is_error)
        payload = result.structured_content
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['id'], product.pk)
        self.assertEqual(payload['results'][0]['match']['relationship'], 'exact_product')
