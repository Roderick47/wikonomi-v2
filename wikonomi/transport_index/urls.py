from django.urls import path

from . import views

app_name = 'transport_index'

urlpatterns = [
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
]
