from django.contrib import admin

from .models import Promotion, PromotionConfirmation, PromotionTarget


class PromotionTargetInline(admin.TabularInline):
    model = PromotionTarget
    extra = 0
    fields = ('product', 'category', 'subcategory')


class PromotionConfirmationInline(admin.TabularInline):
    model = PromotionConfirmation
    extra = 0
    fields = ('user', 'is_still_active', 'updated_at')
    readonly_fields = ('updated_at',)
    can_delete = False


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'business',
        'deal_summary',
        'scope',
        'status_summary',
        'start_at',
        'end_at',
        'is_verified',
        'source',
    )
    list_filter = ('kind', 'deal_type', 'scope', 'source', 'is_verified', 'start_at', 'end_at')
    search_fields = ('title', 'business__name', 'description', 'terms')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('business', 'business_branch', 'created_by')
    inlines = [PromotionTargetInline, PromotionConfirmationInline]

    @admin.display(description='Deal')
    def deal_summary(self, obj):
        return obj.display_deal

    @admin.display(description='Status')
    def status_summary(self, obj):
        return obj.status.title()

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if not change and obj.source == Promotion.Source.COMMUNITY:
            obj.source = Promotion.Source.ADMIN
            obj.is_verified = True
        super().save_model(request, obj, form, change)


@admin.register(PromotionTarget)
class PromotionTargetAdmin(admin.ModelAdmin):
    list_display = ('promotion', 'target_type', 'label')
    search_fields = ('promotion__title', 'product__name', 'category__name', 'subcategory__name')


@admin.register(PromotionConfirmation)
class PromotionConfirmationAdmin(admin.ModelAdmin):
    list_display = ('promotion', 'user', 'is_still_active', 'updated_at')
    list_filter = ('is_still_active', 'updated_at')
    search_fields = ('promotion__title', 'promotion__business__name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
