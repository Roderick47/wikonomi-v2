from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from users.models import Profile
from users import utils


@override_settings(DEFAULT_FROM_EMAIL='Wikonomi <notifications@wikonomi.com>')
class SendVerificationEmailTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.request = self.factory.get('/', HTTP_HOST='wikonomi.com', secure=True)

    @patch('users.utils.send_mail', return_value=1)
    def test_send_verification_email_sends_message_and_generates_token(self, mock_send_mail):
        result = utils.send_verification_email(self.request, self.user, self.profile)

        self.assertTrue(result)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.email_verification_token)
        self.assertIsNotNone(self.profile.email_verification_sent_at)

        kwargs = mock_send_mail.call_args.kwargs
        self.assertEqual(kwargs['recipient_list'], [self.user.email])
        self.assertEqual(kwargs['from_email'], 'Wikonomi <notifications@wikonomi.com>')
        self.assertIn('Verify your Wikonomi email address', kwargs['subject'])
        self.assertIn('https://wikonomi.com/users/verify-email/', kwargs['message'])
        self.assertIn('Verify email address', kwargs['html_message'])

    @patch('users.utils.send_mail')
    def test_send_verification_email_requires_email_address(self, mock_send_mail):
        self.user.email = ''
        self.user.save(update_fields=['email'])

        result = utils.send_verification_email(self.request, self.user, self.profile)

        self.assertFalse(result)
        mock_send_mail.assert_not_called()

    @patch('users.utils.send_mail', side_effect=RuntimeError('smtp unavailable'))
    def test_send_verification_email_returns_false_on_delivery_failure(self, mock_send_mail):
        result = utils.send_verification_email(self.request, self.user, self.profile)

        self.assertFalse(result)
        mock_send_mail.assert_called_once()

    def test_send_verification_email_handles_missing_user(self):
        self.assertFalse(utils.send_verification_email(self.request, None, None))


@override_settings(DEFAULT_FROM_EMAIL='Wikonomi <notifications@wikonomi.com>')
class SendPasswordChangeNotificationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )
        self.request = self.factory.get('/', HTTP_HOST='wikonomi.com', secure=True)

    @patch('users.utils.send_mail', return_value=1)
    def test_password_change_notification_sends_message(self, mock_send_mail):
        result = utils.send_password_change_notification(self.request, self.user)

        self.assertTrue(result)
        kwargs = mock_send_mail.call_args.kwargs
        self.assertEqual(kwargs['recipient_list'], [self.user.email])
        self.assertEqual(kwargs['from_email'], 'Wikonomi <notifications@wikonomi.com>')
        self.assertEqual(kwargs['subject'], 'Your Wikonomi password was changed')
        self.assertIn('no action is needed', kwargs['message'])

    @patch('users.utils.send_mail')
    def test_password_change_notification_requires_email_address(self, mock_send_mail):
        self.user.email = ''
        self.user.save(update_fields=['email'])

        result = utils.send_password_change_notification(self.request, self.user)

        self.assertFalse(result)
        mock_send_mail.assert_not_called()

    @patch('users.utils.send_mail', side_effect=RuntimeError('smtp unavailable'))
    def test_password_change_notification_returns_false_on_delivery_failure(self, mock_send_mail):
        result = utils.send_password_change_notification(self.request, self.user)

        self.assertFalse(result)
        mock_send_mail.assert_called_once()

    def test_password_change_notification_handles_missing_user(self):
        self.assertFalse(utils.send_password_change_notification(self.request, None))


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
