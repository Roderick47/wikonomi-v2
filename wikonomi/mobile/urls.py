from django.urls import path

from . import views

app_name = "mobile"

urlpatterns = [
    path("", views.home, name="home"),
    path("submit/", views.submit, name="submit"),
    path("evidence/<uuid:submission_id>/", views.evidence, name="evidence"),
    path("search/products/", views.search_products, name="search_products"),
    path("search/branches/", views.search_branches, name="search_branches"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("icon-192.png", views.android_icon, {"size": 192}, name="icon_192"),
    path("icon-512.png", views.android_icon, {"size": 512}, name="icon_512"),
    path("icon-maskable-192.png", views.android_icon, {"size": 192, "variant": "maskable"}, name="icon_maskable_192"),
    path("icon-maskable-512.png", views.android_icon, {"size": 512, "variant": "maskable"}, name="icon_maskable_512"),
    path("staging-db-status/", views.staging_db_status, name="staging_db_status"),
]
