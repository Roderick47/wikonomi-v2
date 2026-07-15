from django.contrib import admin

from .models import CabDriver, CabStatus


@admin.register(CabDriver)
class CabDriverAdmin(admin.ModelAdmin):
    list_display = (
        'display_name',
        'whatsapp_number',
        'vehicle_type',
        'vehicle_plate',
        'profile_completeness',
        'is_verified',
        'is_active_listing',
        'created_at',
    )
    list_filter = (
        'vehicle_type',
        'profile_completeness',
        'is_verified',
        'is_active_listing',
        'created_at',
    )
    search_fields = ('display_name', 'whatsapp_number', 'vehicle_plate', 'home_area')
    readonly_fields = ('slug', 'created_at')
    ordering = ('display_name',)


@admin.register(CabStatus)
class CabStatusAdmin(admin.ModelAdmin):
    list_display = (
        'driver',
        'availability',
        'area_label',
        'latitude',
        'longitude',
        'last_updated',
    )
    list_filter = ('availability', 'last_updated')
    search_fields = ('driver__display_name', 'driver__whatsapp_number', 'area_label')
    readonly_fields = ('last_updated',)
