from django.urls import path

from . import views

app_name = 'transport_index'

urlpatterns = [
    path('', views.transport_index, name='index'),
    path('', views.transport_index, name='cab_list'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('setup/<str:token>/', views.setup_profile, name='setup_profile'),
    path('<slug:slug>/', views.cab_profile, name='cab_profile'),
    path('<slug:slug>/contact/', views.cab_contact, name='cab_contact'),
]
