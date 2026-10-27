from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings

from .security import DEFAULT_CSP_REPORT_ONLY, SecurityHeadersMiddleware


class SecurityHeadersMiddlewareTests(SimpleTestCase):
    def _response(self, policy=DEFAULT_CSP_REPORT_ONLY):
        middleware = SecurityHeadersMiddleware(lambda request: HttpResponse('ok'))
        with override_settings(WIKONOMI_CSP_REPORT_ONLY_POLICY=policy):
            return middleware(object())

    def test_csp_report_only_header_is_trimmed(self):
        response = self._response("default-src 'self'; ")
        value = response['Content-Security-Policy-Report-Only']
        self.assertEqual(value, "default-src 'self';")
        self.assertEqual(value, value.strip())

    def test_permissions_policy_is_present(self):
        response = self._response()
        self.assertEqual(
            response['Permissions-Policy'],
            'camera=(self), geolocation=(self), microphone=()',
        )
