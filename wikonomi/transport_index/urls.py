from django.urls import path

from . import views

app_name = 'transport_index'

urlpatterns = [
    path('', views.transport_index, name='index'),
    # Backward-compatible URL name used by shared templates and older links.
    # Keep it pointing at the new canonical transport landing page.
    path('', views.transport_index, name='cab_list'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
]
