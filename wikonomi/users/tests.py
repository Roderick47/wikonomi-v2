from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class FormFeedbackPresentationTests(TestCase):
    """Server-side validation must be visible and anchored outside inputs."""

    def test_login_invalid_credentials_show_form_error(self):
        response = self.client.post(reverse('login'), {
            'username': 'unknown-user',
            'password': 'incorrect-password',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertContains(response, 'class="wk-form-alert" role="alert"')
        self.assertContains(response, 'Please enter a correct username and password')

    def test_signup_invalid_fields_show_errors_below_inputs(self):
        response = self.client.post(reverse('signup'), {
            'username': '',
            'first_name': '',
            'last_name': '',
            'email': 'not-an-email',
            'password1': '',
            'password2': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="wk-field-error"')
        self.assertContains(response, 'This field is required.')

    def test_change_password_errors_use_below_field_style(self):
        user = User.objects.create_user(username='feedback-user', password='InitialPass123!')
        self.client.force_login(user)
        response = self.client.post(reverse('change_password'), {
            'old_password': 'incorrect',
            'new_password1': 'AnotherStrongPass123!',
            'new_password2': 'AnotherStrongPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertContains(response, 'class="wk-field-error"')

    def test_delete_account_invalid_password_shows_inline_message(self):
        user = User.objects.create_user(username='delete-feedback', password='InitialPass123!')
        self.client.force_login(user)
        response = self.client.post(reverse('delete_account'), {'password': 'incorrect'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="wk-field-error" role="alert"')
        self.assertContains(response, 'Incorrect password. Account deletion cancelled.')
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
