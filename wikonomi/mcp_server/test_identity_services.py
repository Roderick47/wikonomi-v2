from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Business, Product
from mcp_server.identity_services import (
    find_or_create_product,
    get_product,
    submit_structured_price,
)
from mcp_server.models import MCPUserAccess
from mcp_server.permissions import ALL_SCOPES, MCPActor


class MCPStructuredIdentityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mcp-identity-user', password='testpass123')
        self.actor = MCPActor(
            user=self.user,
            role=MCPUserAccess.Role.CONTRIBUTOR,
            scopes=tuple(ALL_SCOPES),
            client_id='identity-test-client',
        )
        self.business = Business.objects.create(name='Identity Store', slug='identity-store')

    def _resolve(self, **overrides):
        data = {
            'actor': self.actor,
            'name': 'Trukai Rice',
            'brand': 'Trukai',
            'package_quantity': Decimal('1'),
            'package_unit': 'kg',
            'pack_count': 1,
            'barcode': '',
            'create_if_missing': True,
        }
        data.update(overrides)
        return find_or_create_product(**data)

    def test_barcode_matches_existing_product_even_when_name_differs(self):
        first = self._resolve(barcode='9401234567890')
        second = self._resolve(
            name='Trukai Long Grain Rice',
            barcode='9401234567890',
        )

        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(second['match_basis'], 'barcode')
        self.assertEqual(first['product']['id'], second['product']['id'])

    def test_explicit_package_size_keeps_one_and_five_kg_products_distinct(self):
        one_kg = self._resolve()
        five_kg = self._resolve(
            package_quantity=Decimal('5'),
            package_unit='kg',
        )

        self.assertTrue(one_kg['created'])
        self.assertTrue(five_kg['created'])
        self.assertNotEqual(one_kg['product']['id'], five_kg['product']['id'])
        self.assertEqual(one_kg['product']['structured_identity']['package_quantity'], '1.000')
        self.assertEqual(five_kg['product']['structured_identity']['package_quantity'], '5.000')

    def test_get_product_exposes_structured_identity(self):
        resolved = self._resolve(
            barcode='1234567890123',
            variant='Jasmine',
        )

        payload = get_product(resolved['product']['id'])
        identity = payload['structured_identity']

        self.assertEqual(identity['brand'], 'Trukai')
        self.assertEqual(identity['variant'], 'Jasmine')
        self.assertEqual(identity['barcode'], '1234567890123')
        self.assertEqual(identity['package_unit'], 'kg')
        self.assertEqual(identity['pack_count'], 1)

    def test_structured_price_resolves_identity_before_creating_report(self):
        result = submit_structured_price(
            actor=self.actor,
            data={
                'product_name': 'Roots Rice',
                'brand': 'Roots',
                'barcode': '9988776655443',
                'package_quantity': Decimal('5'),
                'package_unit': 'kg',
                'pack_count': 1,
                'business_id': self.business.pk,
                'price': Decimal('42.50'),
                'currency': 'PGK',
                'notes': 'Observed on shelf',
            },
            ai={'provider': 'OpenAI', 'model': 'test-model'},
        )

        product = Product.objects.get(pk=result['product_id'])
        self.assertEqual(product.identity.brand, 'Roots')
        self.assertEqual(product.identity.normalized_barcode, '9988776655443')
        self.assertEqual(product.identity.package_quantity, Decimal('5.000'))
        self.assertEqual(result['price'], '42.50')
        self.assertEqual(result['product_resolution']['status'], 'created')
