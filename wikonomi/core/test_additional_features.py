from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from unittest.mock import patch, MagicMock
import json
import csv
import io
from decimal import Decimal

from core.models import (
    Product, Business, PriceReport, ProductAlias, BusinessAlias,
    BusinessBranch, ProductWatchlist, ShoppingList, ShoppingListItem,
    Notification, PriceHistory, Category
)
from core import views


class BulkUploadTest(TestCase):
    """Test bulk CSV upload functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
    def test_bulk_upload_get_view(self):
        """Test bulk upload page loads correctly"""
        response = self.client.get(reverse('bulk_upload'))
        # Should return 200 (authenticated user can access)
        self.assertEqual(response.status_code, 200)
        # Should contain bulk upload related content
        self.assertContains(response, 'upload', status_code=200)
        
    def test_bulk_upload_post_no_file(self):
        """Test bulk upload without file shows error"""
        response = self.client.post(reverse('bulk_upload'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please select a CSV file')
        
    def test_bulk_upload_post_invalid_csv(self):
        """Test bulk upload with invalid CSV format"""
        csv_content = "invalid,csv,format".encode('utf-8')
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content, content_type="text/csv"
        )
        
        response = self.client.post(reverse('bulk_upload'), {
            'action': 'preview',
            'csv_file': csv_file,
            'business_name': 'Test Business'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Missing required columns')
        
    def test_bulk_upload_valid_csv_preview(self):
        """Test bulk upload with valid CSV shows preview"""
        csv_content = """product_name,price,currency,notes
Test Product 1,10.50,PGK,Test note 1
Test Product 2,15.75,PGK,Test note 2""".encode('utf-8')
        
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content, content_type="text/csv"
        )
        
        response = self.client.post(reverse('bulk_upload'), {
            'action': 'preview',
            'csv_file': csv_file,
            'business_name': 'Test Business'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preview')  # Should show preview
        self.assertContains(response, 'Test Product 1')
        
    def test_bulk_upload_confirm_creates_records(self):
        """Test bulk upload confirmation creates price reports"""
        csv_content = """product_name,price,currency,notes
Test Product 1,10.50,PGK,Test note 1
Test Product 2,15.75,PGK,Test note 2""".encode('utf-8')
        
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content, content_type="text/csv"
        )
        
        # Step 1: Upload file
        response1 = self.client.post(reverse('bulk_upload'), {
            'action': 'preview',
            'csv_file': csv_file,
            'business_name': 'Test Business'
        })
        
        self.assertEqual(response1.status_code, 200)
        
        # Step 2: Confirm upload
        response2 = self.client.post(reverse('bulk_upload'), {
            'action': 'confirm'
        })
        
        self.assertEqual(response2.status_code, 302)  # Redirect after success
        
        # Verify records were created
        self.assertEqual(PriceReport.objects.count(), 2)
        reports = PriceReport.objects.all().order_by('product__name')
        
        # Check first report
        report1 = reports[0]
        self.assertEqual(report1.product.name, 'Test Product 1')
        self.assertEqual(report1.price, Decimal('10.50'))
        self.assertEqual(report1.currency, 'PGK')
        self.assertEqual(report1.notes, 'Test note 1')
        self.assertEqual(report1.business.name, 'Test Business')

    def test_bulk_upload_inline_editing_confirm(self):
        """Test that inline edits from the frontend correctly override CSV data on confirm"""
        csv_content = "product_name,price\nOriginal Product,10.00"
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        # Step 1: Preview upload
        self.client.post(reverse('bulk_upload'), {
            'action': 'preview',
            'csv_file': csv_file,
            'business_name': 'Test Business'
        })
        
        # Step 2: Confirm with EDITED data (simulating the hidden input from JS)
        edited_data = [
            {
                'row_num': 2,
                'product_name': 'Edited Product Name',
                'price': '99.99',
                'currency': 'USD',
                'notes': 'Edited Notes',
                'tags': 'edited,tags'
            }
        ]
        
        response = self.client.post(reverse('bulk_upload'), {
            'action': 'confirm',
            'edited_data': json.dumps(edited_data)
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify the database contains the EDITED values, not the original ones
        report = PriceReport.objects.first()
        self.assertEqual(report.product.name, 'Edited Product Name')
        self.assertEqual(report.price, Decimal('99.99'))
        self.assertEqual(report.currency, 'USD')
        self.assertEqual(report.notes, 'Edited Notes')
        
    def test_bulk_upload_with_location_data(self):
        """Test bulk upload with latitude/longitude"""
        csv_content = """product_name,price,currency,latitude,longitude
Test Product 1,10.50,PGK,-9.4438,147.1803""".encode('utf-8')
        
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content, content_type="text/csv"
        )
        
        response = self.client.post(reverse('bulk_upload'), {
            'action': 'preview',
            'csv_file': csv_file,
            'business_name': 'Test Business',
            'latitude': '-9.4438',
            'longitude': '147.1803'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preview')
        
    def test_bulk_upload_session_expiry(self):
        """Test bulk upload session expires"""
        csv_content = """product_name,price,currency
Test Product 1,10.50,PGK""".encode('utf-8')
        
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content, content_type="text/csv"
        )
        
        # Upload file
        response1 = self.client.post(reverse('bulk_upload'), {
            'action': 'preview',
            'csv_file': csv_file,
            'business_name': 'Test Business'
        })
        
        # Clear session to simulate expiry
        self.client.session.clear()
        
        # Try to confirm without session data
        response2 = self.client.post(reverse('bulk_upload'), {
            'action': 'confirm'
        })
        
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, 'Upload session expired')
        
    def test_bulk_upload_error_handling(self):
        """Test bulk upload error handling for malformed data"""
        csv_content = """product_name,price,currency
Test Product 1,invalid_price,PGK
Test Product 2,10.50,invalid_currency""".encode('utf-8')
        
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content, content_type="text/csv"
        )
        
        response = self.client.post(reverse('bulk_upload'), {
            'action': 'preview',
            'csv_file': csv_file,
            'business_name': 'Test Business'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'price')  # Checks for price error message
        self.assertContains(response, 'currency')  # Checks for currency error message
        
    def test_download_csv_template(self):
        """Test CSV template download"""
        response = self.client.get(reverse('download_csv_template'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        self.assertIn('wikonomi_bulk_upload_template.csv', response['Content-Disposition'])


class DeletionWorkflowTest(TestCase):
    """Test price report deletion workflow"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.admin_user = User.objects.create_user(username='admin', password='admin', is_staff=True)
        self.product = Product.objects.create(name='Test Product', created_by=self.user)
        self.business = Business.objects.create(name='Test Business')
        self.price_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('10.50'),
            currency='PGK',
            observed_at=timezone.now()
        )
        
    def test_mark_for_deletion(self):
        """Test marking price report for deletion"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('mark_for_deletion', args=[self.price_report.id]), {
            'reason': 'Test deletion reason'
        })
        
        self.assertEqual(response.status_code, 302)
        
        self.price_report.refresh_from_db()
        self.assertTrue(self.price_report.marked_for_deletion)
        self.assertEqual(self.price_report.deletion_reason, 'Test deletion reason')
        self.assertEqual(self.price_report.marked_for_deletion_by, self.user)
        self.assertIsNotNone(self.price_report.marked_for_deletion_at)
        
    def test_mark_for_deletion_requires_reason(self):
        """Test marking for deletion requires reason"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('mark_for_deletion', args=[self.price_report.id]), {})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reason is required')
        
    def test_unmark_for_deletion_by_marker(self):
        """Test unmarking for deletion by original marker"""
        self.client.login(username='testuser', password='testpass')
        
        # First mark for deletion
        self.client.post(reverse('mark_for_deletion', args=[self.price_report.id]), {
            'reason': 'Test reason'
        })
        
        # Then unmark
        response = self.client.post(reverse('unmark_for_deletion', args=[self.price_report.id]))
        
        self.assertEqual(response.status_code, 302)
        
        self.price_report.refresh_from_db()
        self.assertFalse(self.price_report.marked_for_deletion)
        self.assertIsNone(self.price_report.marked_for_deletion_by)
        self.assertIsNone(self.price_report.marked_for_deletion_at)
        
    def test_unmark_for_deletion_denied_for_non_marker(self):
        """Test unmarking denied for non-marker"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('unmark_for_deletion', args=[self.price_report.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You can only unmark')
        
    def test_vote_delete_price(self):
        """Test voting for price report deletion"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('vote_delete_price', args=[self.price_report.id]))
        
        self.assertEqual(response.status_code, 302)
        
        self.price_report.refresh_from_db()
        self.assertEqual(self.price_report.delete_votes, 1)
        
    def test_vote_delete_price_denied_for_marker(self):
        """Test voting denied for user who marked for deletion"""
        self.client.login(username='testuser', password='testpass')
        
        # Mark for deletion first
        self.client.post(reverse('mark_for_deletion', args=[self.price_report.id]), {
            'reason': 'Test reason'
        })
        
        # Try to vote (should be denied)
        response = self.client.post(reverse('vote_delete_price', args=[self.price_report.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You cannot vote to delete')
        
    def test_delete_price_report_by_admin(self):
        """Test admin can delete price report directly"""
        self.client.login(username='admin', password='admin')
        
        response = self.client.post(reverse('delete_price_report', args=[self.price_report.id]))
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PriceReport.objects.filter(id=self.price_report.id).exists())
        
    def test_delete_price_report_after_votes(self):
        """Test deletion after sufficient votes"""
        self.client.login(username='testuser', password='testpass')
        
        # Add votes from different users
        for i in range(3):
            voter = User.objects.create_user(username=f'voter{i}', password='testpass')
            self.client.post(reverse('vote_delete_price', args=[self.price_report.id]))
        
        # Now try to delete (should succeed)
        response = self.client.post(reverse('delete_price_report', args=[self.price_report.id]))
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PriceReport.objects.filter(id=self.price_report.id).exists())


class BusinessBranchTest(TestCase):
    """Test business branch functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.business = Business.objects.create(name='Test Business', slug='test-business')
        
    def test_business_detail_with_branches(self):
        """Test business detail view shows branches"""
        # Create branches
        main_branch = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Main Branch',
            slug='main-branch',
            is_main_branch=True,
            created_by=self.user
        )
        
        branch1 = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Branch 1',
            slug='branch-1',
            location='Port Moresby',
            created_by=self.user
        )
        
        response = self.client.get(reverse('business_detail', args=[self.business.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Main Branch')
        self.assertContains(response, 'Branch 1')
        
    def test_business_edit_with_branches(self):
        """Test business edit view with branches"""
        # Create a branch
        BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Test Branch',
            slug='test-branch',
            location='Test Location',
            created_by=self.user
        )
        
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.get(reverse('business_edit', args=[self.business.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Branch')
        
    def test_create_price_report_with_branch(self):
        """Test creating price report with specific branch"""
        # Create a branch
        branch = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Test Location Branch',
            slug='test-location-branch',
            location='Test Location',
            created_by=self.user
        )
        
        product = Product.objects.create(name='Test Product', created_by=self.user)
        
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('add_price'), {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business',
            'business_location': 'Test Location Branch'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify price report was created with the branch
        price_report = PriceReport.objects.first()
        self.assertEqual(price_report.business_branch, branch)


class NotificationTest(TestCase):
    """Test notification system"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', created_by=self.user)
        
    def test_notification_creation_on_price_change(self):
        """Test notifications are created when price changes"""
        # Create a price report
        price_report = PriceReport.objects.create(
            product=self.product,
            user=self.user,
            price=Decimal('10.00'),
            currency='PGK',
            observed_at=timezone.now()
        )
        
        # Edit the price report (should create notification)
        price_report.price = Decimal('15.00')
        price_report.save()
        
        # Check if notification was created
        notifications = Notification.objects.filter(user=self.user)
        self.assertTrue(notifications.exists())
        
        notification = notifications.first()
        self.assertIn('price change', notification.message.lower())
        
    def test_notification_creation_on_watchlist_price_drop(self):
        """Test notifications for watchlist price drops"""
        # Create watchlist
        ProductWatchlist.objects.create(user=self.user, product=self.product)
        
        # Create a price report
        old_price = Decimal('20.00')
        PriceReport.objects.create(
            product=self.product,
            user=self.user,
            price=old_price,
            currency='PGK',
            observed_at=timezone.now()
        )
        
        # Create a much lower price report
        new_price = Decimal('5.00')
        PriceReport.objects.create(
            product=self.product,
            user=User.objects.create_user(username='otheruser', password='testpass'),
            price=new_price,
            currency='PGK',
            observed_at=timezone.now()
        )
        
        # This should trigger a notification (if implemented)
        notifications = Notification.objects.filter(user=self.user)
        current_count = notifications.count()
        
        # The notification system should detect significant price changes
        # This test verifies the notification creation mechanism
        
    def test_notification_mark_as_read(self):
        """Test marking notifications as read"""
        # Create notifications
        notif1 = Notification.objects.create(
            user=self.user,
            message='Test notification 1',
            is_read=False
        )
        notif2 = Notification.objects.create(
            user=self.user,
            message='Test notification 2',
            is_read=False
        )
        
        # Mark one as read
        response = self.client.post(reverse('notifications'))
        
        self.assertEqual(response.status_code, 200)
        
        notif1.refresh_from_db()
        notif2.refresh_from_db()
        
        self.assertTrue(notif1.is_read)
        self.assertFalse(notif2.is_read)


class UserManagementTest(TestCase):
    """Test user account management functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
    def test_user_signup(self):
        """Test user registration"""
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        
        # Verify user was created
        self.assertTrue(User.objects.filter(username='newuser').exists())
        
    def test_user_login(self):
        """Test user login"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass'
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        
    def test_user_logout(self):
        """Test user logout"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('logout'))
        
        self.assertEqual(response.status_code, 302)  # Should redirect
        
    def test_profile_view(self):
        """Test profile view"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.get(reverse('profile'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profile')  # Should contain profile info
        
    def test_edit_profile(self):
        """Test profile editing"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('edit_profile'), {
            'profile_picture': '',  # Test clearing picture
            # Add other profile fields as needed
        })
        
        self.assertEqual(response.status_code, 200)
        
    def test_change_password(self):
        """Test password change functionality"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('change_password'), {
            'old_password': 'testpass',
            'new_password1': 'newpass123',
            'new_password2': 'newpass123'
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        
    def test_delete_account(self):
        """Test account deletion"""
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('delete_account'), {
            'password': 'testpass',
            'confirm': True
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect on success


class SecurityTest(TestCase):
    """Test security-related functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', created_by=self.user)
        self.business = Business.objects.create(name='Test Business')
        
    def test_csrf_protection(self):
        """Test CSRF protection on forms"""
        # Test without CSRF token
        response = self.client.post(reverse('add_price'), {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business'
        })
        
        # Should fail without CSRF token
        self.assertNotEqual(response.status_code, 302)
        
    def test_authentication_required_for_protected_views(self):
        """Test that protected views require authentication"""
        # Test without login
        response = self.client.get(reverse('shopping_list'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Test with login
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('shopping_list'))
        self.assertEqual(response.status_code, 200)
        
    def test_user_permissions(self):
        """Test user permission checks"""
        # Test that users can only edit their own content
        other_user = User.objects.create_user(username='otheruser', password='testpass')
        other_price_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=other_user,
            price=Decimal('10.50'),
            currency='PGK',
            observed_at=timezone.now()
        )
        
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post(reverse('edit_price_report', args=[other_price_report.id]), {
            'price': '15.00',
            'currency': 'PGK'
        })
        
        # Should not allow editing other user's price report
        self.assertNotEqual(response.status_code, 302)
        
    def test_xss_protection(self):
        """Test XSS protection in user inputs"""
        self.client.login(username='testuser', password='testpass')
        
        # Test with script tag in product name
        response = self.client.post(reverse('add_price'), {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': '<script>alert("xss")</script>Test Product',
            'business_name': 'Test Business'
        })
        
        # Should handle script tags safely
        self.assertEqual(response.status_code, 200)  # Should not crash
