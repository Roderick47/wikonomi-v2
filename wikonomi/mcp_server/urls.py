from django.urls import path

from . import views


app_name = 'mcp_server'

urlpatterns = [
    path('consent/', views.oauth_consent, name='oauth_consent'),
]
