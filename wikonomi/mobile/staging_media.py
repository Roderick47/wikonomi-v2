"""Build an R2 configuration ONLY for a private, separate staging bucket.

Never infer credentials from AWS_* (production) environment variables.
"""
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

BUCKET = "wikonomi-mobile-staging"
STAGING_R2_KEYS = (
    "STAGING_R2_ACCESS_KEY_ID",
    "STAGING_R2_SECRET_ACCESS_KEY",
    "STAGING_R2_ENDPOINT_URL",
    "STAGING_R2_BUCKET_NAME",
)


def staging_media_storage(environ):
    values = {key: environ.get(key, "").strip() for key in STAGING_R2_KEYS}
    if not any(values.values()):
        return {"BACKEND": "django.core.files.storage.FileSystemStorage"}, False
    if not all(values.values()):
        raise ImproperlyConfigured(
            "Set all four STAGING_R2_* variables together, or none."
        )
    if values["STAGING_R2_BUCKET_NAME"] != BUCKET:
        raise ImproperlyConfigured(
            "Refusing storage: staging must use its own wikonomi-mobile-staging bucket."
        )
    endpoint = urlsplit(values["STAGING_R2_ENDPOINT_URL"])
    if (endpoint.scheme != "https"
            or not re.fullmatch(
                r"[a-fA-F0-9]{32}\.r2\.cloudflarestorage\.com",
                endpoint.hostname or "",
            )
            or endpoint.username or endpoint.password or endpoint.port
            or endpoint.path not in ("", "/") or endpoint.query or endpoint.fragment):
        raise ImproperlyConfigured(
            "STAGING_R2_ENDPOINT_URL must be your account's HTTPS Cloudflare R2 endpoint."
        )
    return {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "access_key": values["STAGING_R2_ACCESS_KEY_ID"],
            "secret_key": values["STAGING_R2_SECRET_ACCESS_KEY"],
            "bucket_name": BUCKET,
            "endpoint_url": values["STAGING_R2_ENDPOINT_URL"].rstrip("/"),
            "region_name": "auto",
            "signature_version": "s3v4",
            "querystring_auth": True,
            "default_acl": None,
            "file_overwrite": False,
            "object_parameters": {"CacheControl": "private, no-store"},
        },
    }, True
