from django.urls import path

from . import views

app_name = "mobile"

urlpatterns = [
    path("", views.home, name="home"),
    path("submit/", views.submit, name="submit"),
    path("search/products/", views.search_products, name="search_products"),
    path("search/branches/", views.search_branches, name="search_branches"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
]
