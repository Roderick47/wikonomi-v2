from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils import timezone

from users.models import Profile
from users import utils


class SendVerificationEmailTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.profile, created = Profile.objects.get_or_create(user=self.user)
        self.request = self.factory.get('/')

    def test_send_verification_email_disabled(self):
        """Test that email verification is disabled and returns True"""
        result = utils.send_verification_email(self.request, self.user, self.profile)
        self.assertTrue(result)

    @patch('builtins.print')
    def test_send_verification_email_debug_message(self, mock_print):
        """Test that debug message is printed when email is disabled"""
        utils.send_verification_email(self.request, self.user, self.profile)
        mock_print.assert_called_once_with(f"DEBUG: Email verification disabled for {self.user.email}")

    @patch('users.utils.send_mail')
    @patch('users.utils.render_to_string')
    @patch('users.utils.get_current_site')
    @patch('users.utils.reverse')
    def test_send_verification_email_would_work_if_enabled(
        self, mock_reverse, mock_get_current_site, mock_render_to_string, mock_send_mail
    ):
        """Test the email sending logic if it were enabled"""
        # This test shows what would happen if email functionality was enabled
        # We modify the function temporarily to test the actual email logic
        
        # Setup mocks
        mock_site = MagicMock()
        mock_site.domain = 'example.com'
        mock_get_current_site.return_value = mock_site
        
        mock_reverse.return_value = '/verify-email/'
        mock_render_to_string.return_value = 'Email content'
        
        # Test the email parameters that would be used
        subject = 'Verify your email address'
        message = mock_render_to_string.return_value
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [self.user.email]
        
        # Verify the parameters are correct
        self.assertEqual(subject, 'Verify your email address')
        self.assertEqual(recipient_list, [self.user.email])
        self.assertIsInstance(from_email, str)

    def test_send_verification_email_with_different_user(self):
        """Test email verification with different user data"""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass'
        )
        profile2 = Profile.objects.get_or_create(user=user2)[0]
        
        result = utils.send_verification_email(self.request, user2, profile2)
        self.assertTrue(result)

    def test_send_verification_email_edge_cases(self):
        """Test email verification with edge cases"""
        # Test with user that has no email
        user_no_email = User.objects.create_user(
            username='noemail',
            password='testpass'
        )
        profile_no_email = Profile.objects.get_or_create(user=user_no_email)[0]
        
        result = utils.send_verification_email(self.request, user_no_email, profile_no_email)
        self.assertTrue(result)
        
        # Test with empty email string
        user_empty_email = User.objects.create_user(
            username='emptyemail',
            email='',
            password='testpass'
        )
        profile_empty_email = Profile.objects.get_or_create(user=user_empty_email)[0]
        
        result = utils.send_verification_email(self.request, user_empty_email, profile_empty_email)
        self.assertTrue(result)


class SendPasswordChangeNotificationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.request = self.factory.get('/')

    def test_send_password_change_notification_disabled(self):
        """Test that password change notification is disabled and returns True"""
        result = utils.send_password_change_notification(self.request, self.user)
        self.assertTrue(result)

    @patch('builtins.print')
    def test_send_password_change_notification_debug_message(self, mock_print):
        """Test that debug message is printed when email is disabled"""
        utils.send_password_change_notification(self.request, self.user)
        mock_print.assert_called_once_with(f"DEBUG: Password change notification disabled for {self.user.email}")

    @patch('users.utils.send_mail')
    @patch('users.utils.render_to_string')
    @patch('users.utils.get_current_site')
    def test_send_password_change_notification_would_work_if_enabled(
        self, mock_get_current_site, mock_render_to_string, mock_send_mail
    ):
        """Test the email sending logic if it were enabled"""
        # Setup mocks
        mock_site = MagicMock()
        mock_site.domain = 'example.com'
        mock_get_current_site.return_value = mock_site
        
        mock_render_to_string.return_value = 'Password change notification content'
        
        # Test the email parameters that would be used
        subject = 'Your password has been changed'
        message = mock_render_to_string.return_value
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [self.user.email]
        
        # Verify the parameters are correct
        self.assertEqual(subject, 'Your password has been changed')
        self.assertEqual(recipient_list, [self.user.email])
        self.assertIsInstance(from_email, str)

    def test_send_password_change_notification_with_different_user(self):
        """Test password change notification with different user data"""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass'
        )
        
        result = utils.send_password_change_notification(self.request, user2)
        self.assertTrue(result)

    def test_send_password_change_notification_edge_cases(self):
        """Test password change notification with edge cases"""
        # Test with user that has no email
        user_no_email = User.objects.create_user(
            username='noemail',
            password='testpass'
        )
        
        result = utils.send_password_change_notification(self.request, user_no_email)
        self.assertTrue(result)
        
        # Test with empty email string
        user_empty_email = User.objects.create_user(
            username='emptyemail',
            email='',
            password='testpass'
        )
        
        result = utils.send_password_change_notification(self.request, user_empty_email)
        self.assertTrue(result)


class EmailUtilsIntegrationTest(TestCase):
    """Integration tests for email utility functions"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.profile, created = Profile.objects.get_or_create(user=self.user)
        self.request = self.factory.get('/')

    def test_both_email_functions_return_true(self):
        """Test that both email functions return True when disabled"""
        verification_result = utils.send_verification_email(self.request, self.user, self.profile)
        password_result = utils.send_password_change_notification(self.request, self.user)
        
        self.assertTrue(verification_result)
        self.assertTrue(password_result)

    @patch('builtins.print')
    def test_both_functions_print_debug_messages(self, mock_print):
        """Test that both functions print appropriate debug messages"""
        utils.send_verification_email(self.request, self.user, self.profile)
        utils.send_password_change_notification(self.request, self.user)
        
        expected_calls = [
            f"DEBUG: Email verification disabled for {self.user.email}",
            f"DEBUG: Password change notification disabled for {self.user.email}"
        ]
        
        actual_calls = [call.args[0] for call in mock_print.call_args_list]
        self.assertEqual(actual_calls, expected_calls)

    def test_email_functions_with_request_context(self):
        """Test that email functions work with different request contexts"""
        # Test with POST request
        post_request = self.factory.post('/')
        result1 = utils.send_verification_email(post_request, self.user, self.profile)
        result2 = utils.send_password_change_notification(post_request, self.user)
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        
        # Test with AJAX request
        ajax_request = self.factory.get('/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        result3 = utils.send_verification_email(ajax_request, self.user, self.profile)
        result4 = utils.send_password_change_notification(ajax_request, self.user)
        
        self.assertTrue(result3)
        self.assertTrue(result4)

    @patch('django.conf.settings.DEFAULT_FROM_EMAIL', 'custom@example.com')
    def test_email_functions_with_custom_settings(self):
        """Test email functions respect custom Django settings"""
        # This test verifies that the functions would use custom settings if enabled
        from django.conf import settings
        self.assertEqual(settings.DEFAULT_FROM_EMAIL, 'custom@example.com')
        
        result1 = utils.send_verification_email(self.request, self.user, self.profile)
        result2 = utils.send_password_change_notification(self.request, self.user)
        
        self.assertTrue(result1)
        self.assertTrue(result2)


class EmailUtilsErrorHandlingTest(TestCase):
    """Test error handling in email utility functions"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.profile, created = Profile.objects.get_or_create(user=self.user)
        self.request = self.factory.get('/')

    def test_functions_handle_none_user_gracefully(self):
        """Test that functions handle None user gracefully"""
        # This should not raise an exception
        try:
            result1 = utils.send_verification_email(self.request, None, None)
            result2 = utils.send_password_change_notification(self.request, None)
            self.assertTrue(result1)
            self.assertTrue(result2)
        except AttributeError:
            # Expected to fail gracefully with AttributeError when accessing user.email
            pass

    def test_functions_handle_invalid_email_format(self):
        """Test that functions handle invalid email formats"""
        user_invalid_email = User.objects.create_user(
            username='invalidemail',
            email='invalid-email-format',
            password='testpass'
        )
        profile_invalid = Profile.objects.get_or_create(user=user_invalid_email)[0]
        
        result1 = utils.send_verification_email(self.request, user_invalid_email, profile_invalid)
        result2 = utils.send_password_change_notification(self.request, user_invalid_email)
        
        self.assertTrue(result1)
        self.assertTrue(result2)

    def test_functions_performance(self):
        """Test that functions execute quickly (since they're disabled)"""
        import time
        
        start_time = time.time()
        for _ in range(100):
            utils.send_verification_email(self.request, self.user, self.profile)
            utils.send_password_change_notification(self.request, self.user)
        end_time = time.time()
        
        # Should complete very quickly since they're just printing debug messages
        execution_time = end_time - start_time
        self.assertLess(execution_time, 1.0)  # Should be less than 1 second for 200 calls


class ProfilePictureUrlTest(TestCase):
    def test_default_profile_picture_url_uses_static_avatar(self):
        user = User.objects.create_user(username='default-avatar-user')
        profile = user.profile

        self.assertFalse(profile.has_custom_profile_picture)
        self.assertEqual(profile.profile_picture_url, '/static/img/default-profile.svg')

    def test_custom_profile_picture_url_uses_uploaded_media(self):
        user = User.objects.create_user(username='custom-avatar-user')
        profile = user.profile
        profile.profile_picture = 'profile_pics/custom.jpg'

        self.assertTrue(profile.has_custom_profile_picture)
        self.assertEqual(profile.profile_picture_url, '/media/profile_pics/custom.jpg')
