from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Product

from .models import ProductDuplicateCandidate, ProductIdentity
from .services import (
    create_or_match_product,
    ensure_product_identity,
    find_best_product,
    normalize_barcode,
    parse_product_identity,
)


class ProductIdentityParsingTests(TestCase):
    def test_equivalent_mass_units_share_identity_signature(self):
        one_kg = parse_product_identity('Trukai Rice 1kg')
        thousand_g = parse_product_identity('Trukai Rice 1000 grams')

        self.assertEqual(one_kg.identity_signature, thousand_g.identity_signature)
        self.assertEqual(one_kg.package_quantity, Decimal('1'))
        self.assertEqual(one_kg.package_unit, 'kg')
        self.assertEqual(thousand_g.package_quantity, Decimal('1000'))
        self.assertEqual(thousand_g.package_unit, 'g')

    def test_pack_structure_is_not_collapsed_into_total_volume(self):
        multipack = parse_product_identity('Water 6 x 250ml')
        bottle = parse_product_identity('Water 1.5L')

        self.assertNotEqual(multipack.identity_signature, bottle.identity_signature)
        self.assertEqual(multipack.pack_count, 6)
        self.assertEqual(bottle.pack_count, 1)

    def test_barcode_normalization_removes_spacing_and_hyphens(self):
        self.assertEqual(normalize_barcode(' 9300-123 456 '), '9300123456')


class ProductIdentityMatchingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='catalog-tester', password='testpass')

    def make_product(self, name, **identity):
        product = Product.objects.create(
            name=name,
            slug=name.lower().replace(' ', '-'),
            created_by=self.user,
        )
        ensure_product_identity(product, **identity)
        return product

    def test_new_products_get_inferred_identity_record(self):
        product = Product.objects.create(name='Besta Tuna 185g', slug='besta-tuna-185g')

        identity = ProductIdentity.objects.get(product=product)
        self.assertEqual(identity.package_quantity, Decimal('185'))
        self.assertEqual(identity.package_unit, 'g')

    def test_barcode_match_beats_different_text_name(self):
        existing = self.make_product(
            'Trukai Jasmine Rice 1kg',
            barcode='1234567890123',
            brand='Trukai',
        )

        match = find_best_product(
            'Jasmine Premium Rice 1000g',
            barcode='1234 5678 90123',
            brand='Trukai',
        )

        self.assertEqual(match.product, existing)
        self.assertEqual(match.basis, 'barcode')
        self.assertTrue(match.exact)

    def test_equivalent_units_match_structured_identity(self):
        existing = self.make_product('Trukai Rice 1kg')

        match = find_best_product('Trukai Rice 1000 grams')

        self.assertEqual(match.product, existing)
        self.assertEqual(match.basis, 'structured_identity')
        self.assertTrue(match.exact)

    def test_different_pack_size_does_not_fuzzy_match(self):
        self.make_product('Trukai Rice 1kg')

        match = find_best_product('Trukai Rice 5kg')

        self.assertIsNone(match.product)

    def test_close_compatible_name_creates_review_candidate_instead_of_silent_merge(self):
        existing = self.make_product('Maxicorn 140grams')

        created_product, created, match = create_or_match_product(
            'Maxicorn Snack 140grams',
            created_by=self.user,
        )

        self.assertTrue(created)
        self.assertNotEqual(created_product, existing)
        self.assertGreaterEqual(match.score, Decimal('0.72'))
        candidate = ProductDuplicateCandidate.objects.get()
        self.assertEqual(
            {candidate.source_product_id, candidate.candidate_product_id},
            {existing.id, created_product.id},
        )
        self.assertEqual(candidate.status, ProductDuplicateCandidate.Status.PENDING)

    def test_exact_barcode_reuses_product_and_enriches_identity(self):
        existing = self.make_product(
            'Besta Tuna 185g',
            barcode='9999999999999',
        )

        product, created, match = create_or_match_product(
            'Besta Tuna Can 185 grams',
            barcode='9999999999999',
            brand='Besta',
            created_by=self.user,
            source=ProductIdentity.Source.BULK_IMPORT,
        )

        self.assertFalse(created)
        self.assertEqual(product, existing)
        self.assertEqual(match.basis, 'barcode')
        existing.identity.refresh_from_db()
        self.assertEqual(existing.identity.brand, 'Besta')
        self.assertEqual(existing.identity.normalized_barcode, '9999999999999')
