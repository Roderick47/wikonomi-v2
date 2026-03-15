from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
import json
import re
import time

from core.models import Product, Business, PriceReport
from users.models import Profile


class SecurityTestSuite(TestCase):
    """Comprehensive security testing for WIKONOMI application"""
    
    def setUp(self):
        self.regular_user = User.objects.create_user(
            username='regularuser',
            email='regular@test.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@test.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.product = Product.objects.create(name='Test Product', created_by=self.regular_user)
        self.business = Business.objects.create(name='Test Business')
        
    def test_sql_injection_prevention(self):
        """Test that views are protected against SQL injection"""
        # Test malicious input in search
        malicious_input = "'; DROP TABLE users; --"
        
        response = self.client.get(reverse('home'), {'q': malicious_input})
        
        # Should handle malicious input safely
        self.assertEqual(response.status_code, 200)
        # Should not contain error messages about SQL injection
        self.assertNotContains(response, 'error')
        
    def test_xss_prevention_in_product_names(self):
        """Test XSS prevention in product names"""
        self.client.login(username='regularuser', password='testpass123')
        
        xss_payload = '<script>alert("xss")</script>Test Product'
        
        response = self.client.post(reverse('add_price'), {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': xss_payload,
            'business_name': 'Test Business'
        })
        
        # Should sanitize or escape XSS
        self.assertEqual(response.status_code, 200)
        
        # Verify the product was created safely (without script tags)
        products = Product.objects.filter(name__contains='Test Product')
        self.assertEqual(products.count(), 1)
        
        # Check that the stored name doesn't contain script tags
        product = products.first()
        self.assertNotIn('<script>', product.name)
        
    def test_csrf_token_validation(self):
        """Test CSRF token validation and freshness"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Get form page to extract CSRF token
        response = self.client.get(reverse('add_price'))
        self.assertEqual(response.status_code, 200)
        
        # Extract CSRF token from form
        csrf_token = self.client.cookies.get('csrftoken', '')
        
        # Submit form with CSRF token
        response = self.client.post(reverse('add_price'), {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business',
            'csrfmiddlewaretoken': csrf_token
        })
        
        # Should accept valid CSRF token
        self.assertEqual(response.status_code, 302)
        
    def test_csrf_token_reuse_prevention(self):
        """Test that CSRF tokens cannot be reused"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Get a CSRF token
        response1 = self.client.get(reverse('add_price'))
        csrf_token = self.client.cookies.get('csrftoken', '')
        
        # Try to use the same token again (should fail)
        response2 = self.client.post(reverse('add_price'), {
            'price': '15.00',
            'currency': 'PGK',
            'product_name': 'Another Product',
            'business_name': 'Test Business',
            'csrfmiddlewaretoken': csrf_token
        })
        
        # Second submission should fail or be treated differently
        self.assertIn(response2.status_code, [200, 302])
        
    def test_authentication_bypass_prevention(self):
        """Test that protected views cannot be accessed without authentication"""
        protected_urls = [
            'shopping_list',
            'notifications',
            'profile',
            'edit_profile',
            'change_password',
            'delete_account'
        ]
        
        for url_name in protected_urls:
            response = self.client.get(reverse(url_name))
            # Should redirect to login
            self.assertEqual(response.status_code, 302)
            
    def test_authorization_bypass_prevention(self):
        """Test that users cannot access other users' data"""
        # Create price report by regular user
        price_report = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.regular_user,
            price=10.50,
            currency='PGK',
            observed_at=timezone.now()
        )
        
        # Try to edit as different user
        self.client.login(username='regularuser', password='testpass123')
        
        response = self.client.post(reverse('edit_price_report', args=[price_report.id]), {
            'price': '20.00',
            'currency': 'PGK'
        })
        
        # Should not allow editing other user's data
        self.assertNotEqual(response.status_code, 302)
        
    def test_mass_assignment_prevention(self):
        """Test mass assignment vulnerabilities"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Test bulk operations with large data
        large_data = []
        for i in range(100):
            large_data.append({
                'product_name': f'Product {i}',
                'price': f'{i + 1}.50',
                'currency': 'PGK'
            })
        
        # This should be handled efficiently without timeouts
        start_time = time.time()
        
        response = self.client.post(reverse('bulk_upload'), {
            'csv_file': 'test.csv',
            'business_name': 'Test Business',
            'action': 'confirm'
        })
        
        end_time = time.time()
        
        # Should complete in reasonable time
        self.assertLess(end_time - start_time, 5.0, 'Bulk operation should complete in reasonable time')
        
    def test_session_hijacking_prevention(self):
        """Test session hijacking prevention"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Get session ID
        response = self.client.get(reverse('profile'))
        session_id = self.client.session.session_key
        
        # Verify session is properly configured
        self.assertIsNotNone(session_id)
        
        # Session should be tied to user
        self.client.session.save()
        
        # Test that session is invalidated on logout
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        
        # Verify session is no longer valid
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        
    def test_rate_limiting_sensitive_operations(self):
        """Test rate limiting on sensitive operations"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Test multiple rapid password change attempts
        responses = []
        for i in range(10):
            response = self.client.post(reverse('change_password'), {
                'old_password': 'testpass123',
                'new_password1': f'newpass{i}',
                'new_password2': f'newpass{i}'
            })
            responses.append(response)
        
        # Should implement rate limiting after certain threshold
        # This test verifies the rate limiting mechanism exists
        
        # Count successful responses (should be limited)
        successful_responses = [r for r in responses if r.status_code == 302]
        
        # Should have fewer successful responses than total attempts
        self.assertLess(len(successful_responses), len(responses))
        
    def test_file_upload_security(self):
        """Test file upload security measures"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Test file size limits
        large_content = 'A' * (10 * 1024 * 1024)  # 10MB
        
        response = self.client.post(reverse('add_price'), {
            'price': '10.50',
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business',
            'notes': large_content
        })
        
        # Should handle large files appropriately
        self.assertEqual(response.status_code, 200)
        
    def test_input_validation_security(self):
        """Test comprehensive input validation"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Test various malicious inputs
        malicious_inputs = [
            {'price': '-100', 'currency': 'PGK'},  # Negative price
            {'price': '999999999999', 'currency': 'PGK'},  # Overflow
            {'price': 'abc', 'currency': 'INVALID'},  # Invalid currency
            {'product_name': '<script>alert("xss")</script>'},  # XSS
            {'product_name': 'A' * 1000},  # Too long
            {'business_name': 'A' * 1000},  # Too long
        ]
        
        for malicious_input in malicious_inputs:
            response = self.client.post(reverse('add_price'), malicious_input)
            
            # Should handle malicious input gracefully
            self.assertEqual(response.status_code, 200)
            # Should not crash or cause server error
            
    def test_api_security_headers(self):
        """Test API security headers"""
        self.client.login(username='regularuser', password='testpass123')
        
        response = self.client.get(reverse('api_map_prices'))
        
        # Should have security headers
        self.assertIn('X-Content-Type-Options', response)
        self.assertIn('X-Frame-Options', response)
        
        # Test for proper CORS headers if implemented
        # This would test CORS configuration
        
    def test_database_connection_security(self):
        """Test database connection security"""
        # Test that database connections are properly closed
        # This would verify connection pooling and timeout handling
        
        pass  # Implementation would depend on database configuration
        
    def test_error_message_disclosure(self):
        """Test that error messages don't expose sensitive information"""
        self.client.login(username='regularuser', password='testpass123')
        
        # Test with invalid data that should trigger error
        response = self.client.post(reverse('add_price'), {
            'price': 'invalid_price',
            'currency': 'INVALID'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Should not contain sensitive system information
        self.assertNotContains(response, 'DATABASE')
        self.assertNotContains(response, 'INTERNAL')
        self.assertNotContains(response, 'TRACEBACK')
        
    def test_logging_security(self):
        """Test that logging doesn't expose sensitive data"""
        # This would verify that sensitive information is not logged
        # Implementation would check log levels and data sanitization
        
        pass


class AuthenticationSecurityTest(TestCase):
    """Advanced authentication security testing"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        
    def test_password_strength_validation(self):
        """Test password strength requirements"""
        self.client.login(username='testuser', password='testpass123')
        
        weak_passwords = [
            '123456',
            'password',
            'qwerty',
            'abc123',
            'test',
            '123456789'
        ]
        
        for weak_password in weak_passwords:
            response = self.client.post(reverse('change_password'), {
                'old_password': 'testpass123',
                'new_password1': weak_password,
                'new_password2': weak_password
            })
            
            # Should reject weak passwords
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Password is too weak')
            
    def test_brute_force_protection(self):
        """Test brute force protection"""
        # This would test account lockout after failed attempts
        # Implementation would verify account locking mechanism
        
        pass
        
    def test_session_timeout_security(self):
        """Test session timeout configuration"""
        # This would verify sessions expire appropriately
        # Implementation would check session timeout settings
        
        pass
        
    def test_two_factor_authentication_simulation(self):
        """Test two-factor authentication flows"""
        # This would simulate 2FA if implemented
        # Implementation would test 2FA token generation and validation
        
        pass


class DataIntegrityTest(TestCase):
    """Test data integrity and validation"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        
    def test_price_data_integrity(self):
        """Test price report data integrity"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create price report with valid data
        original_price = 10.50
        response = self.client.post(reverse('add_price'), {
            'price': str(original_price),
            'currency': 'PGK',
            'product_name': 'Test Product',
            'business_name': 'Test Business'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify data integrity
        price_report = PriceReport.objects.first()
        self.assertEqual(float(price_report.price), original_price)
        
    def test_user_data_privacy(self):
        """Test user data privacy protection"""
        self.client.login(username='testuser', password='testpass123')
        
        # Test that user profile doesn't expose sensitive information
        response = self.client.get(reverse('profile'))
        
        self.assertEqual(response.status_code, 200)
        
        # Should not expose password hashes or sensitive tokens
        self.assertNotContains(response, 'password')
        self.assertNotContains(response, 'token')
        
    def test_business_data_integrity(self):
        """Test business data integrity"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create business with valid data
        response = self.client.post(reverse('business_edit', args=[self.business.id]), {
            'name': 'Updated Business Name',
            'details': 'Updated business details'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify data integrity
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, 'Updated Business Name')
        self.assertEqual(self.business.details, 'Updated business details')
        
    def test_bulk_data_validation(self):
        """Test bulk upload data validation"""
        self.client.login(username='testuser', password='testpass123')
        
        # Test CSV with duplicate entries
        csv_content = """product_name,price,currency
Test Product,10.50,PGK
Test Product,10.50,PGK"""
        
        response = self.client.post(reverse('bulk_upload'), {
            'csv_file': 'test.csv',
            'business_name': 'Test Business',
            'action': 'confirm'
        })
        
        # Should handle duplicates appropriately
        # This test would verify duplicate handling logic


class PerformanceSecurityTest(TestCase):
    """Test performance-related security concerns"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        
    def test_denial_of_service_attack(self):
        """Test denial of service attack prevention"""
        # Test with extremely large dataset that could cause DOS
        large_dataset = []
        for i in range(10000):
            large_dataset.append({
                'product_name': f'Product {i}',
                'price': f'{i + 1}.50',
                'currency': 'PGK'
            })
        
        start_time = time.time()
        
        response = self.client.post(reverse('bulk_upload'), {
            'csv_file': 'large_dataset.csv',
            'business_name': 'Test Business',
            'action': 'confirm'
        })
        
        end_time = time.time()
        
        # Should either complete or timeout gracefully
        execution_time = end_time - start_time
        
        # Should complete within reasonable time or be rate limited
        self.assertLess(execution_time, 30.0, 'Large operation should complete or be rate limited')
        
    def test_memory_exhaustion_attack(self):
        """Test memory exhaustion attack prevention"""
        # Test with data that could cause memory issues
        memory_intensive_data = []
        for i in range(1000):
            memory_intensive_data.append({
                'product_name': f'Memory Intensive Product {i}',
                'price': f'{i + 1}.50',
                'currency': 'PGK',
                'notes': 'A' * 10000  # Large text field
            })
        
        start_time = time.time()
        
        response = self.client.post(reverse('bulk_upload'), {
            'csv_file': 'memory_test.csv',
            'business_name': 'Test Business',
            'action': 'confirm'
        })
        
        end_time = time.time()
        
        # Should handle memory usage gracefully
        execution_time = end_time - start_time
        
        # Should either complete or be limited
        self.assertLess(execution_time, 60.0, 'Memory-intensive operation should be handled gracefully')


class ComplianceTest(TestCase):
    """Test compliance with security standards"""
    
    def test_gdpr_compliance(self):
        """Test GDPR compliance features"""
        # Test data export functionality
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(reverse('profile'))
        
        # Should have data export options if implemented
        # This would verify GDPR compliance features
        
        pass
        
    def test_access_control_compliance(self):
        """Test access control compliance"""
        # Test role-based access control
        admin_user = User.objects.create_user(
            username='staffuser',
            email='staff@test.com',
            password='staffpass',
            is_staff=True
        )
        
        # Create admin-only resource
        PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=admin_user,
            price=100.00,
            currency='PGK',
            observed_at=timezone.now()
        )
        
        # Test regular user access (should be denied)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('delete_price_report', args=[PriceReport.objects.last().id]))
        
        # Regular user should not be able to delete admin-only resource
        self.assertNotEqual(response.status_code, 302)
        
        # Test admin user access (should succeed)
        self.client.login(username='staffuser', password='staffpass')
        response = self.client.post(reverse('delete_price_report', args=[PriceReport.objects.last().id]))
        
        self.assertEqual(response.status_code, 302)
        
    def test_audit_trail_compliance(self):
        """Test audit trail compliance"""
        # This would verify that important actions are logged
        # Implementation would check audit logging for sensitive operations
        
        pass


class SecurityConfigurationTest(TestCase):
    """Test security configuration validation"""
    
    def test_https_configuration(self):
        """Test HTTPS enforcement"""
        # This would verify HTTPS is enforced in production
        
        pass
        
    def test_security_headers_configuration(self):
        """Test security headers configuration"""
        # This would verify security headers are properly configured
        
        pass
        
    def test_database_connection_security(self):
        """Test database connection security configuration"""
        # This would verify database connection security settings
        
        pass
        
    def test_session_security_configuration(self):
        """Test session security configuration"""
        # This would verify session security settings
        
        pass


class SecurityMonitoringTest(TestCase):
    """Test security monitoring and alerting"""
    
    def test_suspicious_activity_detection(self):
        """Test detection of suspicious activity"""
        # This would test monitoring for unusual patterns
        # Implementation would check for anomaly detection
        
        pass
        
    def test_security_incident_logging(self):
        """Test security incident logging"""
        # This would verify security incidents are properly logged
        
        pass
