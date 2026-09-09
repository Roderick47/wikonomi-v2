from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Business, BusinessBranch, PriceReport, Product

from .business_search_policy import search_businesses
from .smart_search_wrapper import search_wikonomi


@override_settings(WIKONOMI_MCP_PUBLIC_BASE_URL='https://www.wikonomi.com')
class MCPNaturalBusinessSearchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='natural-business-search')
        self.business = Business.objects.create(name='RH Hypermarket', slug='rh-hypermarket-test')
        self.branch = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Vision City',
            slug='rh-vision-city-test',
            address='Vision City Mega Mall, Waigani',
        )
        self.rice = Product.objects.create(name='Natural Search Rice 1kg', slug='natural-search-rice-1kg')
        PriceReport.objects.create(
            product=self.rice,
            business=self.business,
            business_branch=self.branch,
            price=Decimal('9.50'),
            currency='PGK',
            user=self.user,
        )

    def test_combined_business_and_branch_query_returns_matching_branch(self):
        result = search_businesses('RH Vision City')[0]
        self.assertEqual(result['id'], self.business.pk)
        self.assertEqual(result['matching_branches'][0]['id'], self.branch.pk)
        self.assertIn('rh', result['interpreted_query_tokens'])
        self.assertIn('vision', result['interpreted_query_tokens'])

    def test_natural_question_can_discover_business_from_product_data(self):
        result = search_businesses('which supermarkets have recent data for rice')[0]
        self.assertEqual(result['id'], self.business.pk)
        self.assertEqual(result['interpreted_query_tokens'], ['rice'])
        self.assertEqual(result['matching_current_product_count'], 1)
        self.assertEqual(result['matching_branches'][0]['id'], self.branch.pk)

    def test_generic_search_wikonomi_uses_business_intelligence_results(self):
        response = search_wikonomi('Vision City', entity_types=['business'], limit=5)
        self.assertEqual(response['count'], 1)
        result = response['results'][0]
        self.assertEqual(result['id'], self.business.pk)
        self.assertEqual(result['matching_branches'][0]['id'], self.branch.pk)
        self.assertIn('price_coverage', result)
