"""
Production settings for wikonomi project.
"""

from .settings import *
import os

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['wikonomi.com', 'www.wikonomi.com', '.onrender.com']

# Database - Use PostgreSQL on Render
# Keep ASGI persistent connections disabled here too in case this settings
# module is used directly in a future deployment.
if 'DATABASE_URL' in os.environ:
    import dj_database_url
    database_config = dj_database_url.parse(
        os.environ['DATABASE_URL'],
        conn_max_age=0,
        ssl_require=True,
    )
    database_config.setdefault('OPTIONS', {})['options'] = DB_SESSION_OPTIONS
    DATABASES = {'default': database_config}

# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Media files configuration
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Security settings
# SECURE_SSL_REDIRECT is disabled because Render handles SSL termination at the proxy level
# The proxy handles HTTPS->HTTP conversion, so enabling this would cause infinite redirects
# If using a different deployment setup where Django handles HTTPS directly, set to True
SECURE_SSL_REDIRECT = False  # Render handles SSL at the proxy level
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
TRUST_PROXY_HEADERS = True

# Google OAuth2 settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
            'secret': os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET'),
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}
