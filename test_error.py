import os, sys, django
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'wikonomi')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wikonomi.settings')
import wikonomi.settings
wikonomi.settings.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:'
    }
}
wikonomi.settings.STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
django.setup()

from django.core.management import call_command
call_command('migrate', verbosity=0)

from django.contrib.auth.models import User
from core.models import Product, Business, PriceReport, Category
user = User.objects.create(username="testuser")
user2 = User.objects.create(username="marker")
cat = Category.objects.create(name="c1", slug="c1")
prod = Product.objects.create(name="prod1", slug="prod1", category=cat)
bus = Business.objects.create(name="bus1", slug="bus1")

report = PriceReport.objects.create(product=prod, business=bus, user=user, price=10.0, currency="PGK", latitude=0.0, longitude=0.0, marked_for_deletion=True, marked_for_deletion_by=user2)

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from core.views import price_report_detail

factory = RequestFactory()
request = factory.get(f'/price/{report.pk}/')

print("Testing unauthenticated User")
request.user = AnonymousUser()
try:
    response = price_report_detail(request, pk=report.pk)
    response.render()
    print("Render AnonymousUser successful.")
except Exception as e:
    import traceback
    traceback.print_exc()

print("Testing Authenticated Non-Marker User")
request.user = user
try:
    response = price_report_detail(request, pk=report.pk)
    response.render()
    print("Render User successful.")
except Exception as e:
    import traceback
    traceback.print_exc()

print("Testing Authenticated Marker User")
request.user = user2
try:
    response = price_report_detail(request, pk=report.pk)
    response.render()
    print("Render User2 successful.")
except Exception as e:
    import traceback
    traceback.print_exc()
