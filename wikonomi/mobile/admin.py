from django.contrib import admin, messages

from .models import MobileSubmission
from .services import approve_submission, reject_submission


@admin.register(MobileSubmission)
class MobileSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "submitted_at", "product", "business_branch", "price",
        "contributor", "status", "reviewed_by",
    )
    list_filter = ("status", "submitted_at")
    search_fields = (
        "product__name", "business_branch__name",
        "contributor__username",
    )
    readonly_fields = (
        "contributor", "product", "business_branch", "price", "photo",
        "observed_at", "submitted_at", "client_submission_id",
        "status", "published_report", "reviewed_by", "reviewed_at",
    )
    actions = ("approve_selected", "reject_selected")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # Preserve evidence and audit history.

    @admin.action(description="Approve selected price contributions")
    def approve_selected(self, request, queryset):
        count = 0
        for identifier in queryset.values_list("pk", flat=True):
            try:
                if approve_submission(identifier, request.user):
                    count += 1
            except ValueError as exc:
                self.message_user(request, str(exc), messages.ERROR)
        self.message_user(request, f"Approved {count} contribution(s).")

    @admin.action(description="Reject selected price contributions")
    def reject_selected(self, request, queryset):
        count = sum(
            bool(reject_submission(pk, request.user))
            for pk in queryset.values_list("pk", flat=True)
        )
        self.message_user(request, f"Rejected {count} contribution(s).")
