from .settings import *  # noqa: F401,F403


# CI/test-only settings. Production continues to use the normal PostgreSQL
# configuration in settings.py; this module exists so branch checks do not
# need credentials or network access to the production database.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test-ci.sqlite3',  # noqa: F405
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
USE_R2_STORAGE = False
MEDIA_URL = '/media/'
PROMOTIONS_ENABLED = True
