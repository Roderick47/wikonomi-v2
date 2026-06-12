from django.contrib import admin
from .models import Category, Subcategory, BusinessCategory, BusinessSubcategory


class SubcategoryInline(admin.TabularInline):
    model = Subcategory
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_png_specific', 'order']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SubcategoryInline]


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_png_specific', 'order']
    list_filter = ['category', 'is_png_specific']
    search_fields = ['name', 'examples']


class BusinessSubcategoryInline(admin.TabularInline):
    model = BusinessSubcategory
    extra = 0


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [BusinessSubcategoryInline]


@admin.register(BusinessSubcategory)
class BusinessSubcategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'order']
    list_filter = ['category']
    search_fields = ['name']
