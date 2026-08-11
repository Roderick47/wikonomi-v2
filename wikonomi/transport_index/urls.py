from django.urls import path

from . import views

app_name = 'transport_index'

urlpatterns = [
    path('', views.transport_index, name='index'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
]
