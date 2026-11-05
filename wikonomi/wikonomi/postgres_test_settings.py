"""Isolated CI PostgreSQL settings. Refuse execution outside CI.

Never configure this module with production credentials or endpoints.
GitHub Actions starts an ephemeral PostgreSQL container on localhost.
"""
import os

from .test_settings import *  # noqa: F401,F403

if os.environ.get("CI") != "true":
    raise RuntimeError("postgres_test_settings may only run in CI")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "wikonomi_mobile_ci",
        "USER": "wikonomi_ci",
        "PASSWORD": "local-ci-password-only",
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "CONN_MAX_AGE": 0,
    }
}
