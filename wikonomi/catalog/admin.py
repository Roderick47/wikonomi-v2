from django.contrib import admin
from django.utils import timezone

from .models import ProductDuplicateCandidate, ProductIdentity


@admin.register(ProductIdentity)
class ProductIdentityAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'brand',
        'variant',
        'package_quantity',
        'package_unit',
        'pack_count',
        'barcode',
        'source',
    )
    list_filter = ('source', 'package_unit')
    search_fields = (
        'product__name',
        'brand',
        'variant',
        'barcode',
        'normalized_barcode',
        'identity_signature',
    )
    autocomplete_fields = ('product',)
    readonly_fields = ('normalized_barcode', 'identity_signature', 'created_at', 'updated_at')


@admin.register(ProductDuplicateCandidate)
class ProductDuplicateCandidateAdmin(admin.ModelAdmin):
    list_display = (
        'source_product',
        'candidate_product',
        'similarity_score',
        'match_basis',
        'status',
        'created_at',
    )
    list_filter = ('status', 'match_basis')
    search_fields = ('source_product__name', 'candidate_product__name')
    autocomplete_fields = ('source_product', 'candidate_product', 'reviewed_by')
    readonly_fields = ('similarity_score', 'match_basis', 'details', 'created_at', 'updated_at')
    actions = ('mark_confirmed', 'mark_rejected', 'mark_pending')

    @admin.action(description='Mark selected pairs as confirmed duplicates')
    def mark_confirmed(self, request, queryset):
        queryset.update(
            status=ProductDuplicateCandidate.Status.CONFIRMED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description='Mark selected pairs as not duplicates')
    def mark_rejected(self, request, queryset):
        queryset.update(
            status=ProductDuplicateCandidate.Status.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description='Return selected pairs to pending review')
    def mark_pending(self, request, queryset):
        queryset.update(
            status=ProductDuplicateCandidate.Status.PENDING,
            reviewed_by=None,
            reviewed_at=None,
        )
