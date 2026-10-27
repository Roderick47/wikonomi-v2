"""Production security headers that can be rolled out without breaking pages."""

from django.conf import settings


DEFAULT_CSP_REPORT_ONLY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "script-src 'self' 'unsafe-inline' https:; "
    "style-src 'self' 'unsafe-inline' https:; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data: https:; "
    "connect-src 'self' https:; "
    "frame-src 'self' https:; "
    "form-action 'self' https:; "
)


class SecurityHeadersMiddleware:
    """Add conservative browser hardening headers.

    CSP starts in Report-Only mode so violations can be observed before an
    enforcing policy is introduced.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(
            settings,
            'WIKONOMI_CSP_REPORT_ONLY_POLICY',
            DEFAULT_CSP_REPORT_ONLY,
        )
        policy = policy.strip() if policy else ''
        if policy and 'Content-Security-Policy' not in response:
            response.setdefault('Content-Security-Policy-Report-Only', policy)
        response.setdefault(
            'Permissions-Policy',
            'camera=(self), geolocation=(self), microphone=()',
        )
        return response
