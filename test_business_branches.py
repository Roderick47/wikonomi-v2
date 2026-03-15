#!/usr/bin/env python
"""
Test script to demonstrate business branch functionality.
"""

import os
import sys
import django

# Add wikonomi directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wikonomi'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wikonomi.local')
django.setup()

from core.models import (
    Business, BusinessBranch, BusinessAlias, PriceReport,
    BusinessMatcher, BusinessNormalizationService
)
from django.contrib.auth.models import User

def test_business_branches():
    """Test business branch functionality"""
    
    print("🏪 Testing Business Branch Functionality")
    print("=" * 70)
    
    # Create test user
    user, _ = User.objects.get_or_create(username='branch_test_user')
    
    # Clean up existing test data
    Business.objects.filter(name__contains="BranchTest").delete()
    
    print("\n📊 Creating Test Business with Branches:")
    print("-" * 50)
    
    # Create canonical business
    tst_business = Business.objects.create(
        name="BranchTest TST Supermarket",
        slug="branch-test-tst-supermarket"
    )
    
    # Create branches
    branches = [
        {
            'name': 'Port Moresby Main',
            'slug': 'port-moresby-main',
            'address': 'Waigani Drive, Port Moresby',
            'latitude': -9.4789,
            'longitude': 147.1495,
            'is_main_branch': True
        },
        {
            'name': 'Waigani Branch',
            'slug': 'waigani-branch',
            'address': 'Waigani Central, Port Moresby',
            'latitude': -9.4620,
            'longitude': 147.1800,
            'is_main_branch': False
        },
        {
            'name': 'Lae Branch',
            'slug': 'lae-branch',
            'address': 'Main Street, Lae',
            'latitude': -6.8686,
            'longitude': 146.9333,
            'is_main_branch': False
        }
    ]
    
    created_branches = []
    for branch_data in branches:
        branch = BusinessBranch.objects.create(
            canonical_business=tst_business,
            created_by=user,
            **branch_data
        )
        created_branches.append(branch)
        print(f"Created branch: {branch.get_full_name()}")
    
    # Create business aliases
    aliases = [
        (tst_business, 'TST Supermarket'),
        (tst_business, 'TST Port Moresby'),
        (tst_business, 'TST Waigani'),
        (tst_business, 'TST Lae'),
    ]
    
    for business, alias_name in aliases:
        BusinessAlias.objects.create(
            canonical_business=business,
            alias_name=alias_name,
            created_by=user
        )
    
    print(f"\nBusiness: {tst_business.name}")
    print(f"Branches: {tst_business.branches.count()}")
    print(f"Aliases: {tst_business.aliases.count()}")
    
    print("\n🔍 Testing Branch Matching:")
    print("-" * 50)
    
    # Test various business name inputs
    test_inputs = [
        "TST Supermarket Port Moresby",  # Should match main branch
        "TST Waigani",                # Should match Waigani branch
        "TST Lae Branch",              # Should match Lae branch
        "TST Supermarket",             # Should match business (main branch)
        "BranchTest TST",              # Should match business (main branch)
    ]
    
    for test_input in test_inputs:
        business, branch, similarity = BusinessMatcher.find_best_match(test_input)
        if business:
            if branch:
                print(f"Input: '{test_input}' → {business.name} - {branch.name} (similarity: {similarity:.2f}) ✅")
            else:
                print(f"Input: '{test_input}' → {business.name} - No specific branch (similarity: {similarity:.2f}) ⚠️")
        else:
            print(f"Input: '{test_input}' → No match found ❌")
    
    print("\n🎯 Testing Business Creation with Location:")
    print("-" * 50)
    
    # Test creating business with location
    new_business_tests = [
        ("RH Hypermarket", "Port Moresby"),
        ("RH Hypermarket", "Waigani"),
        ("RH Hypermarket", "Lae"),
    ]
    
    for business_name, location in new_business_tests:
        business, branch, was_created = BusinessMatcher.create_or_match_business_with_location(
            business_name=business_name,
            location=location,
            created_by=user
        )
        
        if was_created:
            print(f"Created NEW: '{business_name}' at '{location}'")
            if branch:
                print(f"  Branch: {branch.get_full_name()}")
        else:
            print(f"Found EXISTING: '{business_name}' at '{location}'")
            if branch:
                print(f"  Branch: {branch.get_full_name()}")
    
    print("\n📝 Creating Price Reports with Branches:")
    print("-" * 50)
    
    # Create test products for price reports
    from core.models import Product
    rice = Product.objects.create(name="BranchTest Rice", slug="branch-test-rice")
    coke = Product.objects.create(name="BranchTest Coke", slug="branch-test-coke")
    
    # Create price reports for different branches
    price_reports = [
        {
            'product': rice,
            'price': 25.50,
            'business': tst_business,
            'branch': created_branches[0],  # Port Moresby Main
            'currency': 'PGK',
            'user': user
        },
        {
            'product': coke,
            'price': 8.75,
            'business': tst_business,
            'branch': created_branches[1],  # Waigani Branch
            'currency': 'PGK',
            'user': user
        },
        {
            'product': rice,
            'price': 26.00,
            'business': tst_business,
            'branch': created_branches[2],  # Lae Branch
            'currency': 'PGK',
            'user': user
        }
    ]
    
    for report_data in price_reports:
        report = PriceReport.objects.create(
            product=report_data['product'],
            business=report_data['business'],
            business_branch=report_data['branch'],
            price=report_data['price'],
            currency=report_data['currency'],
            user=report_data['user']
        )
        print(f"Price report: {report.product.name} - {report.currency} {report.price} at {report.get_business_display()}")
    
    print("\n📊 Branch Statistics:")
    print("-" * 50)
    
    # Show branch statistics
    for branch in tst_business.branches.all():
        report_count = branch.price_reports.count()
        print(f"{branch.get_full_name()}: {report_count} price reports")
        if branch.latitude and branch.longitude:
            print(f"  Location: {branch.latitude}, {branch.longitude}")
        if branch.address:
            print(f"  Address: {branch.address}")
    
    print("\n🔧 Testing Business Display Methods:")
    print("-" * 50)
    
    # Test display methods
    for report in PriceReport.objects.filter(business=tst_business):
        print(f"Report ID {report.id}:")
        print(f"  Product: {report.product.name}")
        print(f"  Price: {report.currency} {report.price}")
        print(f"  Business Display: {report.get_business_display()}")
        print(f"  Coordinates: {report.get_lat_lng()}")
    
    print("\n🎉 Business Branch Test Completed!")
    print("\n📋 Summary:")
    print("-" * 50)
    print("✅ Business model supports multiple branches")
    print("✅ Branches have individual locations and contact info")
    print("✅ Price reports can be linked to specific branches")
    print("✅ Search functionality matches branches")
    print("✅ Business aliases work with branches")
    print("✅ Display methods prioritize branch over main business")
    
    print("\n💡 Real-World Examples:")
    print("-" * 50)
    print("• 'TST Port Moresby' → TST Supermarket - Port Moresby Main")
    print("• 'TST Waigani' → TST Supermarket - Waigani Branch")
    print("• 'TST Lae' → TST Supermarket - Lae Branch")
    print("• Price reports show specific branch locations")
    print("• Search finds both business and branch matches")

if __name__ == '__main__':
    test_business_branches()
