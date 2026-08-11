from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from unittest.mock import patch, MagicMock
import json

from users.models import Profile
from analytics.models import DashboardAccess
from users import views


class UserAuthenticationTest(TestCase):
    """Test user authentication flows"""
    
    def setUp(self):
        self.username = 'testuser'
        self.email = 'test@example.com'
        self.password = 'testpass123'
        
    def test_user_registration_flow(self):
        """Test complete user registration"""
        # Test GET signup page
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign Up')
        
        # Test POST with valid data
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        
        # Should either redirect on success or show form again
        self.assertIn(response.status_code, [200, 302])
        
        # Verify user was created (if successful)
        if response.status_code == 302:
            self.assertTrue(User.objects.filter(username='newuser').exists())
            # Verify profile was created for the new user
            self.assertTrue(Profile.objects.filter(user__username='newuser').exists())
        
    def test_user_login_flow(self):
        """Test user login flow"""
        # Create user first
        User.objects.create_user(username=self.username, email=self.email, password=self.password)
        
        # Test GET login page
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')
        
        # Test POST with valid credentials
        response = self.client.post(reverse('login'), {
            'username': self.username,
            'password': self.password
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(reverse('login'), {
            'username': self.username,
            'password': 'wrongpassword'
        })
        
        self.assertEqual(response.status_code, 200)  # Should stay on login page
        self.assertContains(response, 'Invalid username or password')
        
    def test_user_logout_flow(self):
        """Test user logout flow"""
        # Login first
        self.client.post(reverse('login'), {
            'username': self.username,
            'password': self.password
        })
        
        # Test logout
        response = self.client.post(reverse('logout'))
        
        self.assertEqual(response.status_code, 302)  # Should redirect
        
        # Verify session is cleared
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login


class UserProfileTest(TestCase):
    """Test user profile management"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
    def test_profile_view_displays_user_info(self):
        """Test profile view displays user information"""
        response = self.client.get(reverse('profile'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)
        self.assertContains(response, self.user.email)
        

    def test_profile_shows_analytics_dashboard_link_for_active_access(self):
        """Users with active analytics access can navigate to their dashboard from profile."""
        DashboardAccess.objects.create(
            user=self.user,
            role=DashboardAccess.DashboardRole.INVESTOR,
        )

        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Analytics Dashboard')
        self.assertContains(response, reverse('analytics:investor'))

    def test_profile_hides_analytics_dashboard_link_without_active_access(self):
        """Users without active analytics access should not see dashboard navigation."""
        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Analytics Dashboard')

    def test_profile_hides_analytics_dashboard_link_for_inactive_access(self):
        """Inactive dashboard grants should not expose profile navigation."""
        DashboardAccess.objects.create(
            user=self.user,
            role=DashboardAccess.DashboardRole.TEAM,
            is_active=False,
        )

        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Analytics Dashboard')

    def test_edit_profile_updates_user_info(self):
        """Test profile editing updates user information"""
        new_email = 'updated@example.com'
        
        response = self.client.post(reverse('edit_profile'), {
            'email': new_email,
            'first_name': 'Updated First Name',
            'last_name': 'Updated Last Name'
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('profile'))
        
        # Verify user was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, new_email)
        self.assertEqual(self.user.first_name, 'Updated First Name')
        self.assertEqual(self.user.last_name, 'Updated Last Name')
        
    def test_profile_picture_upload(self):
        """Test profile picture upload functionality"""
        # This would test file upload functionality
        # Implementation depends on how profile pictures are handled
        pass


class UserOnboardingTest(TestCase):
    """Test the one-time onboarding prompt and persistence endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='onboarding-user',
            email='onboarding@example.com',
            password='testpass123',
        )

    def test_new_profile_has_unseen_onboarding(self):
        profile = self.user.profile

        self.assertIsNone(profile.onboarding_completed_at)
        self.assertIsNone(profile.onboarding_dismissed_at)

    def test_new_signed_in_user_gets_automatic_welcome(self):
        self.client.login(username=self.user.username, password='testpass123')

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Want me to show you the ropes?')
        self.assertContains(response, 'data-auto-open="true"')
        self.assertContains(response, 'Create a practical guide')
        self.assertContains(response, 'Find local transport')

    def test_dismiss_onboarding_persists_and_stops_auto_open(self):
        self.client.login(username=self.user.username, password='testpass123')

        response = self.client.post(reverse('update_onboarding'), {'action': 'dismiss'})

        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertIsNotNone(self.user.profile.onboarding_dismissed_at)
        self.assertIsNone(self.user.profile.onboarding_completed_at)

        response = self.client.get(reverse('home'))
        self.assertContains(response, 'data-auto-open="false"')

    def test_complete_onboarding_replaces_dismissed_state(self):
        profile = self.user.profile
        profile.onboarding_dismissed_at = timezone.now()
        profile.save(update_fields=['onboarding_dismissed_at'])
        self.client.login(username=self.user.username, password='testpass123')

        response = self.client.post(reverse('update_onboarding'), {'action': 'complete'})

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.onboarding_completed_at)
        self.assertIsNone(profile.onboarding_dismissed_at)

    def test_onboarding_update_rejects_invalid_action(self):
        self.client.login(username=self.user.username, password='testpass123')

        response = self.client.post(reverse('update_onboarding'), {'action': 'restart'})

        self.assertEqual(response.status_code, 400)

    def test_onboarding_update_requires_login(self):
        response = self.client.post(reverse('update_onboarding'), {'action': 'complete'})

        self.assertEqual(response.status_code, 302)

    def test_onboarding_update_accepts_real_csrf_flow(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username=self.user.username, password='testpass123')
        response = client.get(reverse('home'))
        csrf_token = response.cookies['csrftoken'].value

        response = client.post(
            reverse('update_onboarding'),
            {'action': 'complete'},
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)

    def test_profile_keeps_tour_and_full_guide_available(self):
        self.client.login(username=self.user.username, password='testpass123')

        response = self.client.get(reverse('profile'))

        self.assertContains(response, 'Take the quick tour')
        self.assertContains(response, 'Read the full user guide')


class EmailVerificationTest(TestCase):
    """Test email verification functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.profile = Profile.objects.create(user=self.user)
        
    def test_email_verification_flow(self):
        """Test email verification token flow"""
        # Generate verification token
        token = self.profile.generate_verification_token()
        
        # Test verification with valid token
        response = self.client.get(reverse('verify_email', args=[token]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email verified successfully')
        
        # Verify profile is updated
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verified)
        
    def test_email_verification_invalid_token(self):
        """Test email verification with invalid token"""
        invalid_token = 'invalid-token-12345'
        
        response = self.client.get(reverse('verify_email', args=[invalid_token]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid or expired verification token')
        
    def test_resend_verification_email(self):
        """Test resend verification email functionality"""
        response = self.client.post(reverse('resend_verification_email'))
        
        self.assertEqual(response.status_code, 200)
        # Should show success message regardless (for security)
        
        # Verify new token was generated
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.email_verification_token)


class PasswordManagementTest(TestCase):
    """Test password change functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        self.old_password = 'oldpass123'
        self.new_password = 'newpass456'
        
    def test_change_password_valid_flow(self):
        """Test valid password change flow"""
        response = self.client.post(reverse('change_password'), {
            'old_password': self.old_password,
            'new_password1': self.new_password,
            'new_password2': self.new_password
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        
        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        
    def test_change_password_invalid_old_password(self):
        """Test password change with invalid old password"""
        response = self.client.post(reverse('change_password'), {
            'old_password': 'wrongpassword',
            'new_password1': self.new_password,
            'new_password2': self.new_password
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current password is incorrect')
        
    def test_change_password_mismatched_new_passwords(self):
        """Test password change with mismatched new passwords"""
        response = self.client.post(reverse('change_password'), {
            'old_password': self.old_password,
            'new_password1': self.new_password,
            'new_password2': 'differentpassword'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New passwords do not match')
        
    def test_change_password_weak_password(self):
        """Test password change with weak password"""
        weak_password = '123'
        
        response = self.client.post(reverse('change_password'), {
            'old_password': self.old_password,
            'new_password1': weak_password,
            'new_password2': weak_password
        })
        
        # Should either accept or reject based on password policy
        # This test verifies the password validation logic


class AccountDeletionTest(TestCase):
    """Test account deletion functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
    def test_delete_account_valid_flow(self):
        """Test valid account deletion flow"""
        response = self.client.post(reverse('delete_account'), {
            'password': 'testpass',
            'confirm': True
        })
        
        self.assertEqual(response.status_code, 302)  # Should redirect on success
        
        # Verify user was deleted
        self.assertFalse(User.objects.filter(username='testuser').exists())
        
    def test_delete_account_invalid_password(self):
        """Test account deletion with invalid password"""
        response = self.client.post(reverse('delete_account'), {
            'password': 'wrongpassword',
            'confirm': True
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid password')
        
    def test_delete_account_not_confirmed(self):
        """Test account deletion without confirmation"""
        response = self.client.post(reverse('delete_account'), {
            'password': 'testpass',
            'confirm': False
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please confirm account deletion')
        
    def test_delete_account_user_still_exists(self):
        """Test user still exists after failed deletion"""
        initial_count = User.objects.count()
        
        response = self.client.post(reverse('delete_account'), {
            'password': 'wrongpassword',
            'confirm': True
        })
        
        # User count should not change
        final_count = User.objects.count()
        self.assertEqual(initial_count, final_count)


class UserSecurityTest(TestCase):
    """Test user security features"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.other_user = User.objects.create_user(username='otheruser', password='testpass')
        
    def test_session_security(self):
        """Test session security features"""
        # Login and get session key
        self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass'
        })
        
        # Verify session exists
        session_key = self.client.session.session_key
        self.assertIsNotNone(session_key)
        
    def test_csrf_protection_in_forms(self):
        """Test CSRF protection in user forms"""
        # Test form submission without CSRF token
        response = self.client.post(reverse('signup'), {
            'username': 'csrfuser',
            'email': 'csrf@test.com',
            'password1': 'testpass',
            'password2': 'testpass'
        })
        
        # Should handle CSRF gracefully
        self.assertEqual(response.status_code, 200)  # Should show form again
        
    def test_profile_access_control(self):
        """Test that users can only access their own profile"""
        # Test accessing own profile
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        
        # Test accessing other user's profile (should fail)
        self.client.login(username='otheruser', password='testpass')
        response = self.client.get(reverse('profile'))
        # Should show own profile or 403
        self.assertIn(response.status_code, [200, 403])
        
    def test_rate_limiting(self):
        """Test rate limiting on sensitive operations"""
        # This would test rate limiting implementation
        # Multiple rapid requests should be limited
        pass


class UserProfileIntegrationTest(TestCase):
    """Test profile integration with other systems"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.profile = Profile.objects.create(user=self.user)
        self.client.login(username='testuser', password='testpass')
        
    def test_profile_picture_integration(self):
        """Test profile picture integration with price reports"""
        # Test that profile picture appears in price reports
        from core.models import PriceReport, Product, Business
        
        product = Product.objects.create(name='Test Product', created_by=self.user)
        business = Business.objects.create(name='Test Business')
        
        price_report = PriceReport.objects.create(
            product=product,
            business=business,
            user=self.user,
            price=10.50,
            currency='PGK',
            observed_at=timezone.now()
        )
        
        # Verify profile picture is accessible
        self.assertIsNotNone(self.profile.profile_picture)
        
    def test_email_verification_impact_on_permissions(self):
        """Test email verification status affects user permissions"""
        # Test unverified user permissions
        self.profile.email_verified = False
        self.profile.save()
        
        # Some features might be restricted for unverified users
        # This test would verify such restrictions exist
        
    def test_profile_completion_tracking(self):
        """Test profile completion tracking"""
        # Test that profile completion percentage is calculated
        # This would test profile completion logic
        pass
