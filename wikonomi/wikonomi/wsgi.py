"""
WSGI config for wikonomi project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

default_settings = (\n    'wikonomi.production'\n    if 'RENDER' in os.environ or 'DATABASE_URL' in os.environ\n    else 'wikonomi.settings'\n)\nos.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

application = get_wsgi_application()
