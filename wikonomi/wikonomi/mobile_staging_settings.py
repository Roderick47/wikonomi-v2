"""Temporary isolated mobile PWA staging settings.

Do not use in production. Database is ephemeral until a dedicated staging
DATABASE_URL is explicitly provided and reviewed.
"""
import os
from .test_settings import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["wikonomi-mobile-staging.onrender.com", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["https://wikonomi-mobile-staging.onrender.com"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECRET_KEY = os.environ["SECRET_KEY"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/wikonomi-mobile-staging.sqlite3",
    }
}
MEDIA_ROOT = "/tmp/wikonomi-mobile-media"
SITE_VISIT_ANALYTICS_ENABLED = False
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
PROMOTIONS_ENABLED = False
TRANSPORT_INDEX_PUBLIC_ENABLED = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
