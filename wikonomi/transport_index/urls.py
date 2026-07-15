from django.urls import path
from . import views
app_name = 'transport_index'
urlpatterns = [
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('cabs/', views.cab_list, name='cab_list'),
    path('cabs/setup/<str:token>/', views.setup_profile, name='setup_profile'),
    path('cabs/<slug:slug>/', views.cab_profile, name='cab_profile'),
    path('cabs/<slug:slug>/contact/', views.cab_contact, name='cab_contact'),
]
