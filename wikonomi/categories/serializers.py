from rest_framework import serializers
from .models import Category, Subcategory, BusinessCategory, BusinessSubcategory


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ['id', 'name', 'slug', 'examples', 'is_png_specific']


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'subcategories']


class BusinessSubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessSubcategory
        fields = ['id', 'name', 'slug']


class BusinessCategorySerializer(serializers.ModelSerializer):
    subcategories = BusinessSubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = BusinessCategory
        fields = ['id', 'name', 'slug', 'icon', 'subcategories']
