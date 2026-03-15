#!/usr/bin/env python
"""
Test script to demonstrate enhanced search functionality with product normalization.
"""

import os
import sys
import django

# Add the wikonomi directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wikonomi'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wikonomi.local')
django.setup()

from core.models import Product, ProductAlias, Business, PriceReport, ProductMatcher
from django.contrib.auth.models import User
from django.test import RequestFactory
from core.views import _get_prices_queryset, _get_business_queryset

def test_enhanced_search():
    """Test the enhanced search functionality"""
    
    print("🔍 Testing Enhanced Search Functionality")
    print("=" * 60)
    
    # Create test data
    user, _ = User.objects.get_or_create(username='search_test_user')
    
    # Clean up existing test data
    Product.objects.filter(name__contains="SearchTest").delete()
    Business.objects.filter(name__contains="SearchTest").delete()
    
    # Create canonical products
    rice_product = Product.objects.create(
        name="SearchTest Rice",
        slug="searchtest-rice",
        created_by=user
    )
    
    coke_product = Product.objects.create(
        name="SearchTest Coca Cola", 
        slug="searchtest-coca-cola",
        created_by=user
    )
    
    # Create aliases for pattern variations
    aliases = [
        (rice_product, "Rice 1kg"),
        (rice_product, "1kg Rice"),
        (rice_product, "Rice - 1kg"),
        (coke_product, "Coca Cola 500ml"),
        (coke_product, "500ml Coca Cola"),
        (coke_product, "Coca-Cola 500ml"),
    ]
    
    for product, alias_name in aliases:
        ProductAlias.objects.create(
            canonical_product=product,
            alias_name=alias_name,
            created_by=user
        )
    
    # Create test businesses
    business1 = Business.objects.create(
        name="SearchTest Store A",
        slug="searchtest-store-a"
    )
    
    business2 = Business.objects.create(
        name="SearchTest Store B", 
        slug="searchtest-store-b"
    )
    
    # Create price reports
    PriceReport.objects.create(
        product=rice_product,
        business=business1,
        user=user,
        price=10.50,
        currency='PGK'
    )
    
    PriceReport.objects.create(
        product=coke_product,
        business=business2,
        user=user,
        price=8.75,
        currency='PGK'
    )
    
    print("\n📊 Test Data Created:")
    print("-" * 40)
    print(f"Products: {Product.objects.filter(name__contains='SearchTest').count()}")
    print(f"Aliases: {ProductAlias.objects.filter(alias_name__contains='SearchTest').count()}")
    print(f"Businesses: {Business.objects.filter(name__contains='SearchTest').count()}")
    print(f"Price Reports: {PriceReport.objects.filter(product__name__contains='SearchTest').count()}")
    
    # Create request factory for testing
    factory = RequestFactory()
    
    print("\n🔍 Testing Search Queries:")
    print("-" * 40)
    
    test_queries = [
        "Rice 1kg",           # Should match rice product
        "1kg Rice",           # Should match rice product (pattern variation)
        "Coca Cola 500ml",    # Should match coke product
        "500ml Coca Cola",    # Should match coke product (pattern variation)
        "SearchTest Store A", # Should match business
        "Rice",               # Should match rice product (partial)
        "Cola",               # Should match coke product (partial)
    ]
    
    for query in test_queries:
        print(f"\n🔎 Search: '{query}'")
        
        # Test price report search
        request = factory.get(f'/?q={query}')
        prices_qs, sort, lat, lng = _get_prices_queryset(request)
        
        print(f"  Price Reports Found: {prices_qs.count()}")
        for price in prices_qs[:3]:  # Show first 3
            print(f"    - {price.product.name}: {price.currency} {price.price} at {price.business.name if price.business else 'Unknown'}")
        
        # Test business search
        businesses_qs = _get_business_queryset(request)
        print(f"  Businesses Found: {businesses_qs.count()}")
        for business in businesses_qs[:3]:  # Show first 3
            print(f"    - {business.name}")
    
    print("\n🎯 Testing Pattern Matching:")
    print("-" * 40)
    
    # Test specific pattern matching scenarios
    pattern_tests = [
        ("Rice 1kg", "Should find rice product via exact match"),
        ("1kg Rice", "Should find rice product via signature match"),
        ("Coca Cola 500ml", "Should find coke product via exact match"),
        ("500ml Coca Cola", "Should find coke product via signature match"),
        ("Coca-Cola 500ml", "Should find coke product via alias match"),
    ]
    
    for query, expected in pattern_tests:
        request = factory.get(f'/?q={query}')
        prices_qs, sort, lat, lng = _get_prices_queryset(request)
        
        print(f"Query: '{query}'")
        print(f"Expected: {expected}")
        print(f"Results: {prices_qs.count()} price reports found")
        
        if prices_qs.exists():
            products_found = set(price.product.name for price in prices_qs)
            print(f"Products: {', '.join(products_found)}")
            print("✅ PASS")
        else:
            print("❌ FAIL - No results found")
        print()
    
    print("\n📈 Search Performance Summary:")
    print("-" * 40)
    
    # Show how different search methods work
    query = "1kg Rice"
    print(f"Analyzing search for: '{query}'")
    
    # Direct product name search
    direct_matches = Product.objects.filter(name__icontains=query)
    print(f"Direct name matches: {direct_matches.count()}")
    
    # Alias search
    alias_matches = Product.objects.filter(
        aliases__alias_name__icontains=query,
        aliases__is_active=True
    ).distinct()
    print(f"Alias matches: {alias_matches.count()}")
    
    # Signature search
    query_signature = ProductAlias.create_normalized_signature(query)
    signature_matches = Product.objects.filter(
        aliases__signature=query_signature,
        aliases__is_active=True
    ).distinct()
    print(f"Signature matches: {signature_matches.count()}")
    print(f"Query signature: '{query_signature}'")
    
    print("\n✅ Enhanced search functionality test completed!")

if __name__ == '__main__':
    test_enhanced_search()
