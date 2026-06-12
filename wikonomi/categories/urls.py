from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import api_views, views

router = DefaultRouter()
router.register('categories', api_views.CategoryViewSet, basename='category')
router.register('business-categories', api_views.BusinessCategoryViewSet, basename='business-category')

urlpatterns = [
    path('api/subcategories/', views.subcategories_json, name='subcategories_json'),
    path('api/business-subcategories/', views.business_subcategories_json, name='business_subcategories_json'),
    path('api/', include(router.urls)),
]
