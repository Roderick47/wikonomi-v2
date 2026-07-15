from django.contrib import admin
from django.db.models import Count, Sum
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from .models import CabDriver, CabStatus, ContactAttempt, LLMFallbackLog, RouterEvent


@admin.register(CabDriver)
class CabDriverAdmin(admin.ModelAdmin):
    list_display = ('display_name','whatsapp_number','vehicle_type','vehicle_plate','profile_completeness','is_verified','is_active_listing','created_at')
    list_filter = ('vehicle_type','profile_completeness','is_verified','is_active_listing','created_at')
    search_fields = ('display_name','whatsapp_number','vehicle_plate','home_area')
    readonly_fields = ('slug','created_at')
    ordering = ('display_name',)


@admin.register(CabStatus)
class CabStatusAdmin(admin.ModelAdmin):
    list_display = ('driver','availability','area_label','latitude','longitude','last_updated')
    list_filter = ('availability','last_updated')
    search_fields = ('driver__display_name','driver__whatsapp_number','area_label')
    readonly_fields = ('last_updated',)


@admin.register(ContactAttempt)
class ContactAttemptAdmin(admin.ModelAdmin):
    list_display = ('driver','ip_address','created_at')
    search_fields = ('driver__display_name','ip_address')
    readonly_fields = ('created_at',)


@admin.register(LLMFallbackLog)
class LLMFallbackLogAdmin(admin.ModelAdmin):
    list_display = ('created_at','extracted_intent','input_tokens','output_tokens','estimated_cost_usd')
    readonly_fields = ('created_at',)
    change_list_template = 'admin/transport_index/llmfallbacklog/change_list.html'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        extra_context['monthly_cost'] = LLMFallbackLog.objects.filter(created_at__gte=month_start).aggregate(total=Sum('estimated_cost_usd'))['total'] or 0
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(RouterEvent)
class RouterEventAdmin(admin.ModelAdmin):
    list_display = ('created_at','phone_number','stage','message_type')
    list_filter = ('stage','message_type','created_at')
    search_fields = ('phone_number',)
    readonly_fields = ('created_at',)

    def get_urls(self):
        return [path('dashboard/', self.admin_site.admin_view(self.dashboard), name='transport_router_dashboard')] + super().get_urls()

    def dashboard(self, request):
        since = timezone.now() - timezone.timedelta(days=7)
        rows = RouterEvent.objects.filter(created_at__gte=since).values('stage').annotate(count=Count('id')).order_by('stage')
        total = sum(row['count'] for row in rows) or 1
        return TemplateResponse(request, 'admin/transport_index/router_dashboard.html', {'rows': rows, 'total': total})
