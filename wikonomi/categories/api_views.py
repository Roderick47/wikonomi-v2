from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import Category, BusinessCategory
from .serializers import CategorySerializer, BusinessCategorySerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.prefetch_related('subcategories').all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class BusinessCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BusinessCategory.objects.prefetch_related('subcategories').all()
    serializer_class = BusinessCategorySerializer
    permission_classes = [AllowAny]
