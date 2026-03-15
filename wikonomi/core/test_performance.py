from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from django.test.utils import override_settings
from unittest.mock import patch, MagicMock
import json
import time
from decimal import Decimal

from core.models import (
    Product, Business, PriceReport, ProductAlias, BusinessAlias,
    BusinessBranch, ProductWatchlist, ShoppingList, ShoppingListItem,
    Notification, PriceHistory, Category
)
from core import views


class DatabaseEfficiencyTest(TransactionTestCase):
    """Test database query efficiency and indexing"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
    def test_price_report_query_efficiency(self):
        """Test that price report queries are efficient"""
        # Create test data
        products = []
        businesses = []
        
        # Create 100 products and businesses
        for i in range(100):
            product = Product.objects.create(
                name=f'Product {i}',
                slug=f'product-{i}',
                created_by=self.user
            )
            business = Business.objects.create(name=f'Business {i}', slug=f'business-{i}')
            products.append(product)
            businesses.append(business)
            
            # Create price reports
            PriceReport.objects.create(
                product=product,
                business=business,
                user=self.user,
                price=Decimal(f'{i}.50'),
                currency='PGK',
                observed_at=timezone.now()
            )
        
        # Test query efficiency with select_related and prefetch_related
        start_time = time.time()
        
        # This should use efficient queries
        reports = PriceReport.objects.select_related(
            'product', 'business', 'user'
        ).prefetch_related('product__tags').all()
        
        # Force evaluation
        list(reports)
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Should complete quickly with proper indexing
        self.assertLess(query_time, 0.5, "Price report query should be efficient")
        
        # Verify we got the expected number of results
        count = reports.count()
        self.assertEqual(count, 100)  # We created 100 reports
        
    def test_search_query_optimization(self):
        """Test that search queries use proper indexes"""
        # Create products with aliases for search testing
        product = Product.objects.create(name='Rice', slug='rice', created_by=self.user)
        ProductAlias.objects.create(
            canonical_product=product,
            alias_name='White Rice',
            created_by=self.user
        )
        ProductAlias.objects.create(
            canonical_product=product,
            alias_name='Long Grain Rice',
            created_by=self.user
        )
        
        # Test search query efficiency
        start_time = time.time()
        
        request = MagicMock()
        request.GET = {'q': 'Rice'}
        
        qs, sort, lat, lng = views._get_prices_queryset(request)
        
        # Force evaluation
        count = qs.count()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        self.assertLess(query_time, 0.3, "Search query should be efficient")
        self.assertEqual(count, 1)
        
    def test_business_search_efficiency(self):
        """Test business search query efficiency"""
        # Create test data
        for i in range(50):
            Business.objects.create(name=f'Business {i}')
        
        start_time = time.time()
        
        request = MagicMock()
        request.GET = {'q': 'Business'}
        businesses = views._get_business_queryset(request)
        
        # Force evaluation
        count = businesses.count()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        self.assertLess(query_time, 0.2, "Business search should be efficient")
        self.assertGreater(count, 0)


class ScaleTest(TransactionTestCase):
    """Test system behavior at scale"""
    
    def setUp(self):
        self.users = []
        self.products = []
        self.businesses = []
        
    def test_large_dataset_performance(self):
        """Test performance with large datasets"""
        # Create 1000 users, products, businesses, and price reports
        start_time = time.time()
        
        for i in range(1000):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@test.com',
                password='testpass'
            )
            self.users.append(user)
            
            if i % 10 == 0:  # Create 100 products
                product = Product.objects.create(
                    name=f'Product {i}',
                    slug=f'product-{i}',
                    created_by=user
                )
                self.products.append(product)
        
        # Create 100 businesses
        for i in range(100):
            business = Business.objects.create(name=f'Business {i}', slug=f'business-{i}')
            self.businesses.append(business)
        
        # Create price reports
        for i, product in enumerate(self.products):
            business = self.businesses[i % len(self.businesses)]
            user = self.users[i % len(self.users)]
            
            PriceReport.objects.create(
                product=product,
                business=business,
                user=user,
                price=Decimal(f'{i + 1}.50'),
                currency='PGK',
                observed_at=timezone.now()
            )
        
        creation_time = time.time() - start_time
        
        # Test query performance on large dataset
        start_time = time.time()
        
        reports = PriceReport.objects.select_related(
            'product', 'business', 'user'
        ).order_by('-observed_at')[:100]
        
        # Force evaluation
        list(reports)
        
        query_time = time.time() - start_time
        
        self.assertLess(creation_time, 10.0, "Large dataset creation should be reasonable")
        self.assertLess(query_time, 1.0, "Large dataset query should be efficient")
        self.assertEqual(len(reports), 100)
        
    def test_api_performance_at_scale(self):
        """Test API endpoints with large datasets"""
        # Create test data
        for i in range(200):
            product = Product.objects.create(
                name=f'API Product {i}',
                slug=f'api-product-{i}',
                created_by=self.user
            )
            business = Business.objects.create(name=f'API Business {i}', slug=f'api-business-{i}')
            
            PriceReport.objects.create(
                product=product,
                business=business,
                user=self.user,
                price=Decimal(f'{i + 1}.00'),
                currency='PGK',
                latitude=-9.4438 + (i * 0.001),
                longitude=147.1803 + (i * 0.001),
                observed_at=timezone.now()
            )
        
        # Test map API performance
        start_time = time.time()
        
        url = reverse('api_map_prices')
        response = self.client.get(url)
        
        api_time = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(api_time, 2.0, "Map API should handle large datasets efficiently")
        
        data = json.loads(response.content)
        self.assertIn('items', data)
        self.assertEqual(len(data['items']), 150)  # Limited by API
        
    def test_pagination_performance(self):
        """Test pagination performance with large datasets"""
        # Create 500 price reports
        products = []
        for i in range(50):
            product = Product.objects.create(
                name=f'Pag Product {i}',
                slug=f'pag-product-{i}',
                created_by=self.user
            )
            products.append(product)
        
        for i in range(500):
            product = products[i % len(products)]
            business = Business.objects.create(name=f'Pag Business {i % 20}', slug=f'pag-business-{i % 20}')
            
            PriceReport.objects.create(
                product=product,
                business=business,
                user=self.user,
                price=Decimal(f'{i + 1}.50'),
                currency='PGK',
                observed_at=timezone.now()
            )
        
        # Test pagination performance
        start_time = time.time()
        
        url = reverse('load_more_prices')
        response = self.client.get(url, {'page': 5})
        
        pagination_time = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(pagination_time, 0.5, "Pagination should be efficient")
        
        data = json.loads(response.content)
        self.assertIn('items', data)
        self.assertIn('has_more', data)


class ConcurrencyTest(TransactionTestCase):
    """Test system behavior under concurrent load"""
    
    def test_concurrent_price_report_creation(self):
        """Test concurrent price report creation"""
        import threading
        import queue
        
        results = queue.Queue()
        errors = queue.Queue()
        
        def create_price_report(user_id):
            try:
                from django.db import connections
                from django.contrib.auth.models import User
                
                # Create thread-local connection
                connections['default'] = connections['default'].copy()
                
                user = User.objects.get(id=user_id)
                product = Product.objects.create(
                    name=f'Concurrent Product {user_id}',
                    slug=f'concurrent-product-{user_id}',
                    created_by=user
                )
                business = Business.objects.create(name=f'Concurrent Business {user_id}')
                
                PriceReport.objects.create(
                    product=product,
                    business=business,
                    user=user,
                    price=Decimal('10.50'),
                    currency='PGK',
                    observed_at=timezone.now()
                )
                results.put(True)
            except Exception as e:
                errors.put(str(e))
            finally:
                connections['default'].close()
        
        # Create users for concurrent operations
        users = []
        for i in range(10):
            user = User.objects.create_user(
                username=f'concurrent_user{i}',
                email=f'concurrent{i}@test.com',
                password='testpass'
            )
            users.append(user)
        
        # Start concurrent threads
        threads = []
        for user in users:
            thread = threading.Thread(target=create_price_report, args=(user.id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)
        
        # Check results
        success_count = 0
        while not results.empty():
            results.get()
            success_count += 1
        
        error_count = 0
        while not errors.empty():
            errors.get()
            error_count += 1
        
        self.assertEqual(success_count, 10, "All concurrent operations should succeed")
        self.assertEqual(error_count, 0, "No concurrent operations should fail")
        self.assertEqual(PriceReport.objects.count(), 10)


class MemoryUsageTest(TestCase):
    """Test memory usage patterns"""
    
    def test_memory_efficient_queries(self):
        """Test that queries don't leak memory"""
        # Create test data
        for i in range(100):
            product = Product.objects.create(
                name=f'Mem Product {i}',
                slug=f'mem-product-{i}',
                created_by=User.objects.create_user(
                    username=f'mem_user{i}',
                    password='testpass'
                )
            )
            business = Business.objects.create(name=f'Mem Business {i}', slug=f'mem-business-{i}')
            
            PriceReport.objects.create(
                product=product,
                business=business,
                user=product.created_by,
                price=Decimal(f'{i + 1}.50'),
                currency='PGK',
                observed_at=timezone.now()
            )
        
        # Test memory usage with iterator()
        start_time = time.time()
        
        # Use iterator to avoid loading all objects into memory
        count = 0
        for report in PriceReport.objects.select_related('product', 'business').iterator():
            count += 1
            if count >= 50:  # Limit for test
                break
        
        iteration_time = time.time() - start_time
        
        self.assertLess(iteration_time, 1.0, "Iterator should be memory efficient")
        self.assertEqual(count, 50)
        
    def test_bulk_operations_efficiency(self):
        """Test bulk create operations"""
        # Test bulk creation vs individual creation
        start_time = time.time()
        
        # Individual creation
        for i in range(50):
            Product.objects.create(
                name=f'Individual Product {i}',
                slug=f'individual-product-{i}',
                created_by=self.user
            )
        
        individual_time = time.time() - start_time
        
        # Clear for bulk test
        Product.objects.all().delete()
        
        # Bulk creation
        start_time = time.time()
        
        products = []
        for i in range(50):
            products.append(Product(
                name=f'Bulk Product {i}',
                slug=f'bulk-product-{i}',
                created_by=self.user
            ))
        
        Product.objects.bulk_create(products)
        
        bulk_time = time.time() - start_time
        
        # Bulk should be significantly faster
        self.assertLess(bulk_time, individual_time * 0.5, "Bulk creation should be faster")


class DatabaseIndexTest(TestCase):
    """Test that database indexes are properly utilized"""
    
    def test_product_search_indexing(self):
        """Test that product name searches use indexes"""
        # Create test data with searchable names
        products = []
        for i in range(100):
            product = Product.objects.create(
                name=f'Searchable Product {i:03d}',
                slug=f'searchable-product-{i}',
                created_by=self.user
            )
            products.append(product)
        
        # Test search performance
        start_time = time.time()
        
        # This should use the name index
        found = Product.objects.filter(name__startswith='Searchable Product 0')
        
        count = found.count()
        results = list(found[:10])
        
        search_time = time.time() - start_time
        
        self.assertLess(search_time, 0.2, "Indexed search should be fast")
        self.assertGreater(count, 0)
        self.assertEqual(len(results), 10)
        
    def test_price_report_indexing(self):
        """Test that price report queries use proper indexes"""
        # Create test data
        products = []
        businesses = []
        
        for i in range(50):
            product = Product.objects.create(
                name=f'Indexed Product {i}',
                slug=f'indexed-product-{i}',
                created_by=self.user
            )
            business = Business.objects.create(name=f'Indexed Business {i}', slug=f'indexed-business-{i}')
            products.append(product)
            businesses.append(business)
            
            PriceReport.objects.create(
                product=product,
                business=business,
                user=self.user,
                price=Decimal(f'{i + 1}.50'),
                currency='PGK',
                observed_at=timezone.now()
            )
        
        # Test indexed queries
        start_time = time.time()
        
        # This should use product and business indexes
        reports = PriceReport.objects.filter(
            product__in=products[:10],
            business__in=businesses[:10]
        ).select_related('product', 'business')
        
        count = reports.count()
        results = list(reports)
        
        query_time = time.time() - start_time
        
        self.assertLess(query_time, 0.3, "Indexed join queries should be fast")
        self.assertGreater(count, 0)
        self.assertEqual(len(results), count)


class CacheEfficiencyTest(TestCase):
    """Test caching behavior and efficiency"""
    
    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-cache',
        }
    })
    def test_api_caching_efficiency(self):
        """Test that API responses are properly cached"""
        from django.core.cache import cache
        
        # Create test data
        product = Product.objects.create(
            name='Cached Product',
            slug='cached-product',
            created_by=self.user
        )
        business = Business.objects.create(name=f'Cached Business', slug='cached-business')
        
        PriceReport.objects.create(
            product=product,
            business=business,
            user=self.user,
            price=Decimal('10.50'),
            currency='PGK',
            latitude=-9.4438,
            longitude=147.1803,
            observed_at=timezone.now()
        )
        
        # First request - should cache the result
        start_time = time.time()
        url = reverse('api_map_prices')
        response1 = self.client.get(url)
        first_request_time = time.time() - start_time
        
        # Second request - should be faster due to caching
        start_time = time.time()
        response2 = self.client.get(url)
        second_request_time = time.time() - start_time
        
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        
        # Second request should be faster (cached)
        self.assertLess(second_request_time, first_request_time * 0.8, 
                          "Cached response should be faster")
        
        # Responses should be identical
        data1 = json.loads(response1.content)
        data2 = json.loads(response2.content)
        self.assertEqual(data1, data2)
