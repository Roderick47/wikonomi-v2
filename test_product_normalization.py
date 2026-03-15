#!/usr/bin/env python
"""
Test script to demonstrate product normalization with pattern-based matching.
"""

import os
import sys
import django

# Add the wikonomi directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wikonomi'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wikonomi.local')
django.setup()

from core.models import Product, ProductAlias, ProductMatcher, ProductNormalizationService
from django.contrib.auth.models import User

def test_pattern_matching():
    """Test the enhanced pattern-based matching system"""
    
    print("🧪 Testing Product Normalization with Pattern Matching")
    print("=" * 60)
    
    # Create a test user
    user, _ = User.objects.get_or_create(username='test_user')
    
    # Test cases showing different naming patterns
    test_cases = [
        # Basic variations
        ("Rice 1kg", "1kg Rice"),
        ("Sugar 500g", "500g Sugar"),
        ("Coca Cola 500ml", "500ml Coca Cola"),
        
        # With punctuation and spacing variations
        ("Rice - 1kg", "1kg - Rice"),
        ("Coca-Cola 500ml", "500 ml CocaCola"),
        
        # Complex patterns
        ("Coca Cola 6 x 250ml", "6 x 250ml Coca Cola"),
        ("Cooking Oil 2L", "2L Cooking Oil"),
        
        # No size variations
        ("Fresh Bread", "Bread Fresh"),
        ("Tomatoes", "Fresh Tomatoes"),
    ]
    
    print("\n📝 Testing Pattern Recognition:")
    print("-" * 40)
    
    for i, (variant1, variant2) in enumerate(test_cases, 1):
        print(f"\nTest {i}: '{variant1}' vs '{variant2}'")
        
        # Extract components
        comp1 = ProductAlias.extract_product_components(variant1)
        comp2 = ProductAlias.extract_product_components(variant2)
        
        print(f"  Variant 1: Product='{comp1['product_name']}', Size='{comp1['size_info']}'")
        print(f"  Variant 2: Product='{comp2['product_name']}', Size='{comp2['size_info']}'")
        
        # Create signatures
        sig1 = ProductAlias.create_normalized_signature(variant1)
        sig2 = ProductAlias.create_normalized_signature(variant2)
        
        print(f"  Signature 1: '{sig1}'")
        print(f"  Signature 2: '{sig2}'")
        
        # Check if signatures match
        if sig1 == sig2:
            print("  ✅ SIGNATURES MATCH - Perfect normalization!")
        else:
            print("  ❌ Signatures differ")
    
    print("\n🔄 Testing Product Matching:")
    print("-" * 40)
    
    # Clean up any existing test products
    Product.objects.filter(name__contains="Test").delete()
    ProductAlias.objects.filter(alias_name__contains="Test").delete()
    
    # Create canonical products
    canonical_products = {}
    for i, (variant1, variant2) in enumerate(test_cases[:4], 1):  # Test first 4 cases
        product_name = f"Test Product {i}"
        product = Product.objects.create(
            name=product_name,
            slug=f"test-product-{i}",
            created_by=user
        )
        canonical_products[variant1] = product
        
        # Add aliases for both variants
        ProductAlias.objects.create(
            canonical_product=product,
            alias_name=variant1,
            created_by=user
        )
        ProductAlias.objects.create(
            canonical_product=product,
            alias_name=variant2,
            created_by=user
        )
        
        print(f"Created canonical product: '{product_name}'")
        print(f"  Aliases: '{variant1}' and '{variant2}'")
    
    print("\n🎯 Testing Matching Algorithm:")
    print("-" * 40)
    
    # Test matching with variations
    test_inputs = [
        "Rice 1kg",           # Should match Test Product 1
        "1kg Rice",           # Should match Test Product 1  
        "Sugar 500g",         # Should match Test Product 2
        "500g Sugar",         # Should match Test Product 2
        "Coca Cola 500ml",    # Should match Test Product 3
        "500ml Coca Cola",    # Should match Test Product 3
        "Rice - 1kg",         # Should match Test Product 1 (pattern)
        "500 g Sugar",        # Should match Test Product 2 (spacing)
    ]
    
    for test_input in test_inputs:
        product, similarity = ProductMatcher.find_best_match(test_input)
        if product:
            print(f"Input: '{test_input}' → Match: '{product.name}' (similarity: {similarity:.2f})")
        else:
            print(f"Input: '{test_input}' → No match found")
    
    print("\n📊 Summary:")
    print("-" * 40)
    print(f"Total products created: {Product.objects.filter(name__contains='Test').count()}")
    print(f"Total aliases created: {ProductAlias.objects.filter(alias_name__contains='Test').count()}")
    
    # Show signature statistics
    signatures = ProductAlias.objects.filter(alias_name__contains='Test').values_list('signature', flat=True)
    unique_signatures = set(signatures)
    print(f"Unique signatures: {len(unique_signatures)}")
    
    print("\n✅ Pattern-based normalization test completed!")

if __name__ == '__main__':
    test_pattern_matching()
