from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
    path('users/', views.team_dashboard, name='users'),
    path('investor/', views.investor_dashboard, name='investor'),
]
