from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase, TestCase

from .context_processors import notifications_count


class NotificationsContextProcessorTests(SimpleTestCase):
    def test_database_error_does_not_break_authenticated_pages(self):
        request = RequestFactory().get('/')
        request.user = SimpleNamespace(is_authenticated=True)

        with patch('core.models.Notification.objects.filter') as filter_mock:
            filter_mock.return_value.count.side_effect = DatabaseError('not ready')
            context = notifications_count(request)

        self.assertEqual(context, {'unread_notifications_count': 0})


class AuthenticatedPageTests(TestCase):
    def test_authenticated_home_page_loads(self):
        user = get_user_model().objects.create_user(
            username='home-user',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
