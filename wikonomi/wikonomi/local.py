"""
Local development settings for wikonomi project.
"""

from .settings import *
import os

# Override settings for local development
DEBUG = True

# Use SQLite for local development (no password required)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Email backend for local development (console backend to see emails without sending)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable account verification for local development
ACCOUNT_VERIFICATION_REQUIRED = False

# Allow all hosts for local development
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

# Media files for local development
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Static files for local development
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Security settings for local development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

print("🚀 Local development settings loaded")
print("📦 Using SQLite database")
print("📧 Using console email backend")
