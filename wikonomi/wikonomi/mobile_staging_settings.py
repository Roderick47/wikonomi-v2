"""Isolated mobile preview: NEVER point this at Wikonomi production.

Set STAGING_DATABASE_URL only to the internal URL of
wikonomi-mobile-staging-db, not DATABASE_URL from the live service.
Until configured, SQLite storage is disposable on Render's free tier.
"""
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .test_settings import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["wikonomi-mobile-staging.onrender.com", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["https://wikonomi-mobile-staging.onrender.com"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECRET_KEY = os.environ["SECRET_KEY"]

_STAGING_DB_ID = "dpg-db83lvgu01pc73a8atgg-a"
_STAGING_DB_HOSTS = {
    _STAGING_DB_ID,
    _STAGING_DB_ID + ".singapore-postgres.render.com",
}
_STAGING_DB_NAME = "wikonomi_mobile_staging_db"
_STAGING_DB_USER = "wikonomi_mobile_staging_db_user"

staging_url = os.environ.get("STAGING_DATABASE_URL", "").strip()
if staging_url:
    database_config = dj_database_url.parse(staging_url, conn_max_age=0)
    # Fail closed on mistakenly supplied production credentials or DB endpoint.
    if (database_config.get("ENGINE") != "django.db.backends.postgresql"
            or database_config.get("NAME") != _STAGING_DB_NAME
            or database_config.get("USER") != _STAGING_DB_USER
            or database_config.get("HOST") not in _STAGING_DB_HOSTS):
        raise ImproperlyConfigured(
            "STAGING_DATABASE_URL must reference the dedicated mobile staging DB only."
        )
    DATABASES = {"default": database_config}
    MOBILE_STAGING_EPHEMERAL_DB = False
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "/tmp/wikonomi-mobile-staging.sqlite3",
        }
    }
    MOBILE_STAGING_EPHEMERAL_DB = True

MEDIA_ROOT = "/tmp/wikonomi-mobile-media"
# Never reuse the public production R2 bucket.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_URL = "/media/"
USE_R2_STORAGE = False
SITE_VISIT_ANALYTICS_ENABLED = False
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
PROMOTIONS_ENABLED = False
TRANSPORT_INDEX_PUBLIC_ENABLED = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
