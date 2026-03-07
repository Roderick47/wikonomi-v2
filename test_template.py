import os; import django
from django.conf import settings
from django.template import Template, Context
settings.configure(INSTALLED_APPS=[], TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates"}])
django.setup()
try:
    t = Template('{% if user != report.marked_for_deletion_by and not report.deletion_votes.all|slice:":1"|length %}hey{% endif %}')
    print("Template parsed ok")
except Exception as e:
    print(repr(e))
