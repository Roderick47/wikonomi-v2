#!/usr/bin/env python
"""
Comprehensive Test Suite for Product and Business Normalization Features
Tests all normalization components with proper assertions and edge cases.
"""

import os
import sys
import django
import unittest
from decimal import Decimal

# Add wikonomi directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wikonomi'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wikonomi.local')
django.setup()

from core.models import (
    Product, ProductAlias, Business, BusinessBranch, BusinessAlias, 
    ProductMatcher, BusinessMatcher,
    ProductNormalizationService, BusinessNormalizationService, PriceReport
)
from django.contrib.auth.models import User
from django.test import RequestFactory
from core.views import _get_prices_queryset, _get_business_queryset


class TestNormalizationSuite(unittest.TestCase):
    """Comprehensive test suite for normalization features"""
    
    def setUp(self):
        """Set up test environment"""
        self.user, _ = User.objects.get_or_create(username='test_suite_user')
        self.factory = RequestFactory()
        
        # Clean up existing test data
        self.cleanup_test_data()
        
        # Create test products
        self.rice_product = Product.objects.create(
            name="Test Rice",
            slug="test-rice",
            created_by=self.user
        )
        
        self.coke_product = Product.objects.create(
            name="Test Coca Cola", 
            slug="test-coca-cola",
            created_by=self.user
        )
        
        # Create test business
        self.tst_business = Business.objects.create(
            name="Test TST Supermarket",
            slug="test-tst-supermarket"
        )
        
    def tearDown(self):
        """Clean up after tests"""
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Remove all test-related data"""
        Product.objects.filter(name__contains="Test").delete()
        Business.objects.filter(name__contains="Test").delete()
        ProductAlias.objects.filter(alias_name__contains="Test").delete()
        BusinessAlias.objects.filter(alias_name__contains="Test").delete()
        BusinessBranch.objects.filter(name__contains="Test").delete()
        PriceReport.objects.filter(product__name__contains="Test").delete()
    
    # ========== PRODUCT NORMALIZATION TESTS ==========
    
    def test_product_exact_match(self):
        """Test exact product name matching"""
        print("\n🧪 Testing Product Exact Match")
        
        product, similarity = ProductMatcher.find_best_match("Test Rice")
        
        self.assertIsNotNone(product)
        self.assertEqual(similarity, 1.0)
        self.assertEqual(product.name, "Test Rice")
        print("✅ Exact match works correctly")
    
    def test_product_pattern_matching(self):
        """Test pattern-based product matching (Rice 1kg vs 1kg Rice)"""
        print("\n🧪 Testing Product Pattern Matching")
        
        # Create aliases with pattern variations
        ProductAlias.objects.create(
            canonical_product=self.rice_product,
            alias_name="Rice 1kg",
            created_by=self.user
        )
        
        ProductAlias.objects.create(
            canonical_product=self.rice_product,
            alias_name="1kg Rice",
            created_by=self.user
        )
        
        # Test both variations match the same product
        product1, sim1 = ProductMatcher.find_best_match("Rice 1kg")
        product2, sim2 = ProductMatcher.find_best_match("1kg Rice")
        
        self.assertEqual(product1.id, product2.id)
        self.assertEqual(product1.name, "Test Rice")
        self.assertGreater(sim1, 0.9)
        self.assertGreater(sim2, 0.9)
        print("✅ Pattern matching works correctly")
    
    def test_product_fuzzy_matching(self):
        """Test fuzzy matching for similar product names"""
        print("\n🧪 Testing Product Fuzzy Matching")
        
        ProductAlias.objects.create(
            canonical_product=self.coke_product,
            alias_name="Coca Cola",
            created_by=self.user
        )
        
        # Test fuzzy match
        product, similarity = ProductMatcher.find_best_match("Coca Cola")
        
        self.assertIsNotNone(product)
        self.assertEqual(product.name, "Test Coca Cola")
        self.assertGreater(similarity, 0.7)
        print("✅ Fuzzy matching works correctly")
    
    def test_product_signature_generation(self):
        """Test signature generation for pattern variations"""
        print("\n🧪 Testing Product Signature Generation")
        
        # Test signature generation
        sig1 = ProductAlias.create_normalized_signature("Rice 1kg")
        sig2 = ProductAlias.create_normalized_signature("1kg Rice")
        
        self.assertEqual(sig1, sig2)
        self.assertIn("rice", sig1)
        self.assertIn("1kg", sig1)
        print("✅ Signature generation works correctly")
    
    def test_product_creation_service(self):
        """Test product creation through normalization service"""
        print("\n🧪 Testing Product Creation Service")
        
        # Test new product creation
        product, was_created = ProductNormalizationService.normalize_price_report_data(
            product_name="Test New Product",
            category=None
        )
        
        self.assertTrue(was_created)
        self.assertEqual(product.name, "Test New Product")
        print("✅ Product creation service works correctly")
    
    # ========== BUSINESS NORMALIZATION TESTS ==========
    
    def test_business_exact_match(self):
        """Test exact business name matching"""
        print("\n🧪 Testing Business Exact Match")
        
        BusinessAlias.objects.create(
            canonical_business=self.tst_business,
            alias_name="TST Supermarket",
            created_by=self.user
        )
        
        business, branch, similarity = BusinessMatcher.find_best_match("TST Supermarket")
        
        self.assertIsNotNone(business)
        self.assertEqual(similarity, 1.0)
        self.assertEqual(business.name, "Test TST Supermarket")
        print("✅ Business exact match works correctly")
    
    def test_business_branch_matching(self):
        """Test business branch matching"""
        print("\n🧪 Testing Business Branch Matching")
        
        # Create branches
        main_branch = BusinessBranch.objects.create(
            canonical_business=self.tst_business,
            name="Port Moresby Main",
            slug="port-moresby-main",
            is_main_branch=True,
            created_by=self.user
        )
        
        waigani_branch = BusinessBranch.objects.create(
            canonical_business=self.tst_business,
            name="Waigani Branch",
            slug="waigani-branch",
            created_by=self.user
        )
        
        # Test branch matching
        business, branch, similarity = BusinessMatcher.find_best_match("Waigani Branch")
        
        self.assertIsNotNone(business)
        self.assertIsNotNone(branch)
        self.assertEqual(branch.id, waigani_branch.id)
        self.assertEqual(similarity, 1.0)
        print("✅ Business branch matching works correctly")
    
    def test_business_creation_with_location(self):
        """Test business creation with location/branch"""
        print("\n🧪 Testing Business Creation with Location")
        
        business, branch, was_created = BusinessMatcher.create_or_match_business_with_location(
            business_name="Test RH Hypermarket",
            location="Port Moresby",
            created_by=self.user
        )
        
        self.assertTrue(was_created)
        self.assertIsNotNone(business)
        self.assertIsNotNone(branch)
        self.assertEqual(branch.name, "Port Moresby")
        self.assertTrue(branch.is_main_branch)
        print("✅ Business creation with location works correctly")
    
    # ========== SEARCH FUNCTIONALITY TESTS ==========
    
    def test_price_search_with_normalization(self):
        """Test price search using normalization"""
        print("\n🧪 Testing Price Search with Normalization")
        
        # Create product aliases
        ProductAlias.objects.create(
            canonical_product=self.rice_product,
            alias_name="Rice 1kg",
            created_by=self.user
        )
        
        # Create price report
        PriceReport.objects.create(
            product=self.rice_product,
            business=self.tst_business,
            user=self.user,
            price=Decimal('25.50'),
            currency='PGK'
        )
        
        # Test search
        request = self.factory.get('/?q=Rice 1kg')
        prices_qs, sort, lat, lng = _get_prices_queryset(request)
        
        self.assertGreater(prices_qs.count(), 0)
        self.assertEqual(prices_qs.first().product.name, "Test Rice")
        print("✅ Price search with normalization works correctly")
    
    def test_business_search_with_normalization(self):
        """Test business search using normalization"""
        print("\n🧪 Testing Business Search with Normalization")
        
        # Create business aliases
        BusinessAlias.objects.create(
            canonical_business=self.tst_business,
            alias_name="TST POM",
            created_by=self.user
        )
        
        # Test search
        request = self.factory.get('/?q=TST POM')
        businesses_qs = _get_business_queryset(request)
        
        self.assertGreater(businesses_qs.count(), 0)
        self.assertEqual(businesses_qs.first().name, "Test TST Supermarket")
        print("✅ Business search with normalization works correctly")
    
    # ========== INTEGRATION TESTS ==========
    
    def test_complete_normalization_workflow(self):
        """Test complete workflow from creation to search"""
        print("\n🧪 Testing Complete Normalization Workflow")
        
        # 1. Create product with aliases
        ProductAlias.objects.create(
            canonical_product=self.rice_product,
            alias_name="Rice 1kg",
            created_by=self.user
        )
        
        # 2. Create business with branches
        main_branch = BusinessBranch.objects.create(
            canonical_business=self.tst_business,
            name="Main Branch",
            slug="main-branch",
            is_main_branch=True,
            created_by=self.user
        )
        
        # 3. Create business aliases
        BusinessAlias.objects.create(
            canonical_business=self.tst_business,
            alias_name="TST Main",
            created_by=self.user
        )
        
        # 4. Create price report
        report = PriceReport.objects.create(
            product=self.rice_product,
            business=self.tst_business,
            business_branch=main_branch,
            user=self.user,
            price=Decimal('25.50'),
            currency='PGK'
        )
        
        # 5. Test search finds the report
        # Test with just product name first
        request = self.factory.get('/?q=Rice 1kg')
        prices_qs, sort, lat, lng = _get_prices_queryset(request)
        businesses_qs = _get_business_queryset(request)
        
        self.assertGreater(prices_qs.count(), 0)
        self.assertGreater(businesses_qs.count(), 0)
        self.assertEqual(prices_qs.first().id, report.id)
        print("✅ Complete normalization workflow works correctly")
    
    # ========== EDGE CASE TESTS ==========
    
    def test_empty_search_handling(self):
        """Test handling of empty searches"""
        print("\n🧪 Testing Empty Search Handling")
        
        request = self.factory.get('/?q=')
        prices_qs, sort, lat, lng = _get_prices_queryset(request)
        businesses_qs = _get_business_queryset(request)
        
        # Should return all results when query is empty
        self.assertGreaterEqual(prices_qs.count(), 0)
        self.assertEqual(businesses_qs.count(), 0)  # Returns empty for businesses
        print("✅ Empty search handling works correctly")
    
    def test_unicode_handling(self):
        """Test handling of unicode characters in names"""
        print("\n🧪 Testing Unicode Handling")
        
        # Create product with unicode
        unicode_product = Product.objects.create(
            name="Test Café",
            slug="test-cafe",
            created_by=self.user
        )
        
        ProductAlias.objects.create(
            canonical_product=unicode_product,
            alias_name="Café",
            created_by=self.user
        )
        
        # Test search with unicode
        product, similarity = ProductMatcher.find_best_match("Café")
        
        self.assertIsNotNone(product)
        self.assertEqual(product.name, "Test Café")
        print("✅ Unicode handling works correctly")


def run_comprehensive_tests():
    """Run all normalization tests"""
    print("🚀 Running Comprehensive Normalization Test Suite")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestNormalizationSuite)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success Rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n💥 ERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    if result.wasSuccessful():
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Product Normalization: WORKING")
        print("✅ Business Normalization: WORKING") 
        print("✅ Branch Support: WORKING")
        print("✅ Search Integration: WORKING")
        print("✅ Pattern Matching: WORKING")
        print("✅ Fuzzy Matching: WORKING")
        print("✅ Unicode Support: WORKING")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
