from django.contrib import admin
from .models import Category, Product, PriceReport, ProductAlias, Business, BusinessAlias, BusinessBranch

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_by', 'created_at', 'alias_count')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'tags__name')
    list_filter = ('category', 'created_at')
    readonly_fields = ('created_at',)
    
    def alias_count(self, obj):
        return obj.aliases.count()
    alias_count.short_description = 'Aliases'

class ProductAliasInline(admin.TabularInline):
    model = ProductAlias
    extra = 1
    readonly_fields = ('normalized_name', 'created_at')

@admin.register(ProductAlias)
class ProductAliasAdmin(admin.ModelAdmin):
    list_display = ('alias_name', 'canonical_product', 'normalized_name', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active', 'created_at', 'canonical_product')
    search_fields = ('alias_name', 'canonical_product__name', 'normalized_name')
    readonly_fields = ('normalized_name', 'created_at')
    list_editable = ('is_active',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('canonical_product', 'created_by')

class BusinessAliasInline(admin.TabularInline):
    model = BusinessAlias
    extra = 1
    readonly_fields = ('normalized_name', 'created_at')

class BusinessBranchInline(admin.TabularInline):
    model = BusinessBranch
    extra = 1
    readonly_fields = ('created_at',)
    fields = ('name', 'slug', 'address', 'latitude', 'longitude', 'phone', 'email', 'is_main_branch', 'is_active')

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'alias_count', 'branch_count')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    inlines = [BusinessAliasInline, BusinessBranchInline]
    
    def alias_count(self, obj):
        return obj.aliases.count()
    alias_count.short_description = 'Aliases'
    
    def branch_count(self, obj):
        return obj.branches.count()
    branch_count.short_description = 'Branches'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('aliases', 'branches')

@admin.register(BusinessAlias)
class BusinessAliasAdmin(admin.ModelAdmin):
    list_display = ('alias_name', 'canonical_business', 'normalized_name', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active', 'created_at', 'canonical_business')
    search_fields = ('alias_name', 'canonical_business__name', 'normalized_name')
    readonly_fields = ('normalized_name', 'created_at')
    list_editable = ('is_active',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('canonical_business', 'created_by')

@admin.register(BusinessBranch)
class BusinessBranchAdmin(admin.ModelAdmin):
    list_display = ('canonical_business', 'name', 'address', 'is_main_branch', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_main_branch', 'created_at', 'canonical_business')
    search_fields = ('name', 'canonical_business__name', 'address')
    readonly_fields = ('created_at',)
    list_editable = ('is_active',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('canonical_business')

@admin.register(PriceReport)
class PriceReportAdmin(admin.ModelAdmin):
    list_display = ('product', 'price', 'currency', 'business', 'user', 'observed_at')
    list_filter = ('currency', 'observed_at', 'product__category', 'business')
    search_fields = ('product__name', 'user__username', 'notes', 'business__name')
    readonly_fields = ('observed_at', 'updated_at', 'h3_res9', 'h3_res8')
