"""
URL configuration for wikonomi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users import views as user_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Override specific allauth URLs to redirect to custom templates
    path('accounts/login/', user_views.allauth_login_redirect, name='allauth_login_redirect'),
    path('accounts/signup/', user_views.allauth_signup_redirect, name='allauth_signup_redirect'),
    path('accounts/logout/', user_views.allauth_logout_redirect, name='allauth_logout_redirect'),
    path('users/', include('users.urls')),
    path('accounts/', include('allauth.urls')),
    path('categories/', include('categories.urls')),
    path('', include('core.urls')),
    path('analytics/', include('analytics.urls')),
    path('api/comments/', include('comments.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve media files in production (for Render)
if not settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
