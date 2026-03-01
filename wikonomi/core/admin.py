from django.contrib import admin
from .models import Category, Product, PriceReport

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_by', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'tags__name')
    list_filter = ('category',)

@admin.register(PriceReport)
class PriceReportAdmin(admin.ModelAdmin):
    list_display = ('product', 'price', 'currency', 'user', 'observed_at')
    list_filter = ('currency', 'observed_at')
    search_fields = ('product__name', 'user__username', 'notes')
    readonly_fields = ('observed_at', 'updated_at', 'h3_res9', 'h3_res8')
