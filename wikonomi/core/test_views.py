from django.test import TestCase, Client
from django.contrib.auth.models import User, AnonymousUser
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
import json
from decimal import Decimal

from core.models import (
    Product, Business, PriceReport, ProductAlias, BusinessAlias,
    BusinessBranch, ProductWatchlist, ShoppingList, ShoppingListItem,
    Notification, PriceHistory, Category
)
from core import views


class PriceReportCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.anonymous_user = User.objects.get_or_create(username='anonymous')[0]
        self.product = Product.objects.create(name='Test Product', slug='test-product', created_by=self.user)
        self.business = Business.objects.create(name='Test Business')
        self.url = reverse('add_price')
        
    def test_get_context_data_includes_products_and_businesses(self):
        """Test that the view context includes all products and businesses"""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('products', response.context)
        self.assertIn('businesses', response.context)
        self.assertEqual(list(response.context['products']), [self.product])
        self.assertEqual(list(response.context['businesses']), [self.business])

    def test_form_valid_authenticated_user(self):
        """Test form validation with authenticated user"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business',
            'notes': 'Test notes',
            'latitude': '-9.4438',
            'longitude': '147.1803'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        price_report = PriceReport.objects.first()
        self.assertEqual(price_report.user, self.user)
        self.assertEqual(price_report.price, Decimal('10.50'))
        self.assertEqual(price_report.currency, 'PGK')
        self.assertEqual(price_report.product, self.product)
        self.assertEqual(price_report.business, self.business)

    def test_form_valid_anonymous_user(self):
        """Test form validation with anonymous user"""
        data = {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business',
            'notes': 'Test notes'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        price_report = PriceReport.objects.first()
        self.assertEqual(price_report.user.username, 'anonymous')

    def test_form_valid_missing_product_name(self):
        """Test that form validation fails without product name"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': '',
            'business_name': 'Test Business'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PriceReport.objects.exists())

    @patch('core.views.ProductNormalizationService.normalize_price_report_data')
    def test_product_normalization_service_called(self, mock_normalize):
        """Test that product normalization service is called"""
        mock_normalize.return_value = (self.product, False)
        self.client.login(username='testuser', password='testpass')
        data = {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'New Product',
            'business_name': 'Test Business'
        }
        self.client.post(self.url, data)
        mock_normalize.assert_called_once_with(
            product_name='New Product',
            category=None
        )

    @patch('core.views.BusinessNormalizationService.normalize_price_report_data')
    def test_business_normalization_service_called(self, mock_normalize):
        """Test that business normalization service is called"""
        mock_normalize.return_value = (self.business, None, False)
        self.client.login(username='testuser', password='testpass')
        data = {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'New Business',
            'business_location': 'Port Moresby'
        }
        self.client.post(self.url, data)
        mock_normalize.assert_called_once_with(
            business_name='New Business',
            location='Port Moresby'
        )

    def test_tags_processing(self):
        """Test that tags are properly processed and added to product"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business',
            'tags': 'tag1, tag2, tag3'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        product = Product.objects.get(name='Test Product')
        tags = list(product.tags.names())
        self.assertIn('tag1', tags)
        self.assertIn('tag2', tags)
        self.assertIn('tag3', tags)


class SearchFunctionalityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product1 = Product.objects.create(name='Rice', slug='rice', created_by=self.user)
        self.product2 = Product.objects.create(name='Bread', slug='bread', created_by=self.user)
        self.business1 = Business.objects.create(name='Shop A')
        self.business2 = Business.objects.create(name='Store B')
        
        # Create price reports
        self.price1 = PriceReport.objects.create(
            product=self.product1,
            business=self.business1,
            user=self.user,
            price=Decimal('10.00'),
            currency='PGK',
            observed_at=timezone.now()
        )
        self.price2 = PriceReport.objects.create(
            product=self.product2,
            business=self.business2,
            user=self.user,
            price=Decimal('5.00'),
            currency='PGK',
            observed_at=timezone.now()
        )

    def test_get_prices_queryset_no_search(self):
        """Test queryset without search parameters"""
        request = MagicMock()
        request.GET = {}
        qs, sort, lat, lng = views._get_prices_queryset(request)
        self.assertEqual(qs.count(), 2)
        self.assertEqual(sort, 'recent')

    def test_get_prices_queryset_with_query(self):
        """Test queryset with search query"""
        request = MagicMock()
        request.GET = {'q': 'Rice'}
        qs, sort, lat, lng = views._get_prices_queryset(request)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().product, self.product1)

    def test_get_prices_queryset_sort_by_price_asc(self):
        """Test sorting by price ascending"""
        request = MagicMock()
        request.GET = {'sort': 'price_asc'}
        qs, sort, lat, lng = views._get_prices_queryset(request)
        prices = list(qs.values_list('price', flat=True))
        self.assertEqual(prices, [Decimal('5.00'), Decimal('10.00')])

    def test_get_prices_queryset_sort_by_price_desc(self):
        """Test sorting by price descending"""
        request = MagicMock()
        request.GET = {'sort': 'price_desc'}
        qs, sort, lat, lng = views._get_prices_queryset(request)
        prices = list(qs.values_list('price', flat=True))
        self.assertEqual(prices, [Decimal('10.00'), Decimal('5.00')])

    def test_get_prices_queryset_with_location_sort(self):
        """Test sorting by distance with location"""
        request = MagicMock()
        request.GET = {'sort': 'nearest', 'lat': '-9.4438', 'lng': '147.1803'}
        
        # Add location to price reports
        self.price1.latitude = -9.4438
        self.price1.longitude = 147.1803
        self.price1.save()
        
        with patch('core.views.annotate_with_distance') as mock_annotate:
            mock_annotate.return_value = PriceReport.objects.all()
            qs, sort, lat, lng = views._get_prices_queryset(request)
            mock_annotate.assert_called_once()

    def test_get_business_queryset_with_query(self):
        """Test business search functionality"""
        request = MagicMock()
        request.GET = {'q': 'Shop'}
        businesses = views._get_business_queryset(request)
        self.assertEqual(businesses.count(), 1)
        self.assertEqual(businesses.first(), self.business1)

    def test_get_business_queryset_no_query(self):
        """Test business search without query returns none"""
        request = MagicMock()
        request.GET = {}
        businesses = views._get_business_queryset(request)
        self.assertEqual(businesses.count(), 0)

    def test_search_with_product_aliases(self):
        """Test search functionality with product aliases"""
        # Create an alias for rice
        ProductAlias.objects.create(
            canonical_product=self.product1,
            alias_name='White Rice',
            created_by=self.user
        )
        
        request = MagicMock()
        request.GET = {'q': 'White Rice'}
        qs, sort, lat, lng = views._get_prices_queryset(request)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().product, self.product1)


class APIEndpointsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', slug='test-product', created_by=self.user)
        self.business = Business.objects.create(name='Test Business')
        
        # Create price report with location
        self.price = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('10.50'),
            currency='PGK',
            latitude=-9.4438,
            longitude=147.1803,
            observed_at=timezone.now()
        )

    def test_api_map_prices(self):
        """Test map API endpoint"""
        url = reverse('api_map_prices')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('items', data)
        self.assertEqual(len(data['items']), 1)
        
        item = data['items'][0]
        self.assertEqual(item['product'], 'Test Product')
        self.assertEqual(item['price'], 'PGK 10.50')
        self.assertEqual(item['business'], 'Test Business')

    def test_api_map_prices_filters_location(self):
        """Test that map API filters out reports without location"""
        # Create price report without location
        PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('15.00'),
            currency='PGK',
            observed_at=timezone.now()
        )
        
        url = reverse('api_map_prices')
        response = self.client.get(url)
        data = json.loads(response.content)
        self.assertEqual(len(data['items']), 1)  # Only the one with location

    def test_load_more_prices(self):
        """Test load more prices API endpoint"""
        url = reverse('load_more_prices')
        response = self.client.get(url, {'page': 1})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('items', data)
        self.assertIn('has_more', data)
        self.assertIn('current_page', data)
        self.assertIn('total_pages', data)
        
        self.assertEqual(len(data['items']), 1)
        self.assertFalse(data['has_more'])

    def test_load_more_prices_invalid_page(self):
        """Test load more prices with invalid page number"""
        url = reverse('load_more_prices')
        response = self.client.get(url, {'page': 'invalid'})
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertIn('error', data)

    def test_load_more_prices_empty_page(self):
        """Test load more prices with page beyond range"""
        url = reverse('load_more_prices')
        response = self.client.get(url, {'page': 999})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertFalse(data['has_more'])


class HomeViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', slug='test-product', created_by=self.user)
        self.business = Business.objects.create(name='Test Business')
        
        self.price = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('10.50'),
            currency='PGK',
            observed_at=timezone.now()
        )

    def test_home_view_basic(self):
        """Test basic home view functionality"""
        url = reverse('home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('latest_prices', response.context)
        self.assertIn('businesses', response.context)
        self.assertIn('current_sort', response.context)
        self.assertIn('search_query', response.context)

    def test_home_view_with_search(self):
        """Test home view with search query"""
        url = reverse('home')
        response = self.client.get(url, {'q': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['search_query'], 'Test')

    def test_home_view_with_sort(self):
        """Test home view with sort parameter"""
        url = reverse('home')
        response = self.client.get(url, {'sort': 'price_asc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_sort'], 'price_asc')


class WatchlistTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', slug='test-product', created_by=self.user)
        self.client.login(username='testuser', password='testpass')

    def test_toggle_watchlist_add(self):
        """Test adding product to watchlist"""
        url = reverse('toggle_watchlist', args=[self.product.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['watching'])
        
        watchlist = ProductWatchlist.objects.filter(user=self.user, product=self.product)
        self.assertTrue(watchlist.exists())

    def test_toggle_watchlist_remove(self):
        """Test removing product from watchlist"""
        # Add to watchlist first
        ProductWatchlist.objects.create(user=self.user, product=self.product)
        
        url = reverse('toggle_watchlist', args=[self.product.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertFalse(data['watching'])
        
        watchlist = ProductWatchlist.objects.filter(user=self.user, product=self.product)
        self.assertFalse(watchlist.exists())

    def test_toggle_watchlist_requires_login(self):
        """Test that toggle watchlist requires authentication"""
        self.client.logout()
        url = reverse('toggle_watchlist', args=[self.product.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login


class ShoppingListTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', slug='test-product', created_by=self.user)
        self.client.login(username='testuser', password='testpass')

    def test_shopping_lists_view_creates_default_list(self):
        """Test that shopping list view creates default list if none exists"""
        url = reverse('shopping_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        shopping_list = ShoppingList.objects.filter(user=self.user, name="My Shopping List")
        self.assertTrue(shopping_list.exists())

    def test_shopping_lists_view_with_existing_list(self):
        """Test shopping list view with existing list"""
        ShoppingList.objects.create(user=self.user, name="Custom List")
        
        url = reverse('shopping_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('shopping_lists', response.context)
        self.assertIn('active_list', response.context)

    def test_add_to_shopping_list_with_product(self):
        """Test adding product to shopping list"""
        # Create shopping list first
        shopping_list = ShoppingList.objects.create(user=self.user, name="My List")
        
        url = reverse('add_to_shopping_list')
        data = {'product_id': self.product.id}
        response = self.client.post(url, 
                                   data=json.dumps(data), 
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'added')
        self.assertEqual(response_data['item_name'], 'Test Product')
        
        item = ShoppingListItem.objects.filter(shopping_list=shopping_list, product=self.product)
        self.assertTrue(item.exists())

    def test_add_to_shopping_list_with_custom_item(self):
        """Test adding custom item to shopping list"""
        shopping_list = ShoppingList.objects.create(user=self.user, name="My List")
        
        url = reverse('add_to_shopping_list')
        data = {'item_name': 'Custom Item'}
        response = self.client.post(url, 
                                   data=json.dumps(data), 
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'added')
        self.assertEqual(response_data['item_name'], 'Custom Item')

    def test_add_to_shopping_list_creates_list_if_none(self):
        """Test that adding item creates shopping list if none exists"""
        url = reverse('add_to_shopping_list')
        data = {'item_name': 'Test Item'}
        response = self.client.post(url, 
                                   data=json.dumps(data), 
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        shopping_list = ShoppingList.objects.filter(user=self.user)
        self.assertTrue(shopping_list.exists())

    def test_add_to_shopping_list_invalid_input(self):
        """Test adding to shopping list with invalid input"""
        url = reverse('add_to_shopping_list')
        data = {}
        response = self.client.post(url, 
                                   data=json.dumps(data), 
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'error')


class PriceReportEditTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', slug='test-product', created_by=self.user)
        self.business = Business.objects.create(name='Test Business')
        self.price_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('10.00'),
            currency='PGK',
            observed_at=timezone.now()
        )
        self.client.login(username='testuser', password='testpass')

    def test_edit_price_report_creates_history(self):
        """Test that editing price report creates history record"""
        url = reverse('edit_price_report', args=[self.price_report.id])
        data = {
            'price': '15.00',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business',
            'notes': 'Updated notes'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        # Check history was created
        history = PriceHistory.objects.filter(price_report=self.price_report)
        self.assertTrue(history.exists())
        
        history_record = history.first()
        self.assertEqual(history_record.old_price, Decimal('10.00'))
        self.assertEqual(history_record.new_price, Decimal('15.00'))
        self.assertEqual(history_record.changed_by, self.user)

    def test_edit_price_report_updates_product(self):
        """Test editing price report with new product"""
        url = reverse('edit_price_report', args=[self.price_report.id])
        data = {
            'price': '10.00',
            'currency': 'PGK',
            'product_name': 'New Product',
            'business_name': 'Test Business'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        self.price_report.refresh_from_db()
        self.assertEqual(self.price_report.product.name, 'New Product')

    def test_edit_price_report_requires_login(self):
        """Test that editing requires authentication"""
        self.client.logout()
        url = reverse('edit_price_report', args=[self.price_report.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login


class BusinessCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.existing_business = Business.objects.create(name='Existing Business', slug='existing-business')
        self.url = reverse('add_business')

    def test_get_business_create_page_renders_template(self):
        """Test that the business creation page renders correctly"""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'business_create.html')

    def test_get_context_data_includes_businesses(self):
        """Test that the view context includes all existing businesses"""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('businesses', response.context)
        self.assertIn(self.existing_business, response.context['businesses'])

    def test_business_create_with_valid_data(self):
        """Test creating a business with valid data"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'name': 'New Test Business',
            'details': 'This is a test business description'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)  # Redirect to business detail page
        
        # Verify business was created
        new_business = Business.objects.get(name='New Test Business')
        self.assertEqual(new_business.details, 'This is a test business description')
        self.assertEqual(new_business.slug, 'new-test-business')

    def test_business_creates_unique_slug(self):
        """Test that unique slugs are generated for businesses with similar names"""
        self.client.login(username='testuser', password='testpass')
        
        # Create first business
        data1 = {'name': 'Unique Business Name'}
        response1 = self.client.post(self.url, data1)
        self.assertEqual(response1.status_code, 302)
        
        # Create second business with similar name that would generate same slug
        data2 = {'name': 'Unique Business Name'}  # Same name, should be prevented
        response2 = self.client.post(self.url, data2)
        self.assertEqual(response2.status_code, 200)  # Form should be redisplayed with errors
        
        # Verify only one business exists
        businesses = Business.objects.filter(name='Unique Business Name')
        self.assertEqual(businesses.count(), 1)
        business1 = businesses.first()
        self.assertEqual(business1.slug, 'unique-business-name')

    def test_business_slug_generation_with_different_names(self):
        """Test that different business names generate appropriate slugs"""
        self.client.login(username='testuser', password='testpass')
        
        # Create business with special characters
        data = {'name': 'Test & Business Co.'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        new_business = Business.objects.get(name='Test & Business Co.')
        self.assertEqual(new_business.slug, 'test-business-co')

    def test_business_duplicate_prevention_with_normalization(self):
        """Test that similar business names are prevented"""
        self.client.login(username='testuser', password='testpass')
        
        # Try to create business with similar name to existing one
        data = {
            'name': 'Existing Business',  # Same as existing
            'details': 'Duplicate business'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)  # Form should be redisplayed with errors
        
        # Verify no new business was created
        businesses = Business.objects.filter(name='Existing Business')
        self.assertEqual(businesses.count(), 1)  # Only the original exists

    def test_business_duplicate_prevention_with_similar_names(self):
        """Test prevention of very similar business names"""
        self.client.login(username='testuser', password='testpass')
        
        # Try to create business with similar name
        data = {
            'name': 'Existing Business Ltd',  # Very similar to existing
            'details': 'Similar business'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)  # Form should be redisplayed with errors
        
        # Check error message
        self.assertContains(response, 'A business with a similar name already exists')

    def test_business_create_with_special_characters_slug(self):
        """Test slug generation with special characters"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'name': 'Test Business & Co. (Papua New Guinea)!'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        new_business = Business.objects.get(name='Test Business & Co. (Papua New Guinea)!')
        self.assertEqual(new_business.slug, 'test-business-co-papua-new-guinea')

    def test_business_create_without_authentication(self):
        """Test that business creation works without authentication"""
        data = {
            'name': 'Anonymous Business',
            'details': 'Created without login'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)  # Should still work
        
        # Verify business was created
        new_business = Business.objects.get(name='Anonymous Business')
        self.assertEqual(new_business.details, 'Created without login')

    def test_business_create_empty_name_fails(self):
        """Test that creating a business without a name fails"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'name': '',  # Empty name
            'details': 'Business with no name'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)  # Form should be redisplayed
        
        # Verify no business was created
        self.assertFalse(Business.objects.filter(details='Business with no name').exists())

    def test_business_create_redirects_to_detail_page(self):
        """Test that successful business creation redirects to detail page"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'name': 'Redirect Test Business'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        # Get the created business and verify redirect URL
        new_business = Business.objects.get(name='Redirect Test Business')
        expected_url = reverse('business_detail', kwargs={'pk': new_business.pk})
        self.assertRedirects(response, expected_url)

    def test_business_create_with_minimal_data(self):
        """Test creating a business with only required fields"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'name': 'Minimal Business'
            # No details field
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        new_business = Business.objects.get(name='Minimal Business')
        self.assertEqual(new_business.details, '')  # Should be empty string

    def test_business_create_case_insensitive_duplicate(self):
        """Test that case variations of existing business names are prevented"""
        self.client.login(username='testuser', password='testpass')
        
        # Try to create business with different case
        data = {
            'name': 'existing business',  # Lowercase version
            'details': 'Case variation test'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)  # Form should be redisplayed with errors
        
        # Check error message
        self.assertContains(response, 'A business with a similar name already exists')

    def test_business_create_with_whitespace_slug(self):
        """Test slug generation with extra whitespace"""
        self.client.login(username='testuser', password='testpass')
        data = {
            'name': '  Test Business  With  Spaces  '
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        
        # Django forms strip whitespace, so the saved name will be trimmed
        new_business = Business.objects.get(name='Test Business  With  Spaces')
        self.assertEqual(new_business.slug, 'test-business-with-spaces')
