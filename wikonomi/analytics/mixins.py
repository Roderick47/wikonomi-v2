from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .models import DashboardAccess


class DashboardAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Require a DashboardAccess role and expose the resolved dashboard mode."""

    required_dashboard_roles = ()
    view_mode = None

    def get_required_dashboard_roles(self):
        if self.required_dashboard_roles:
            return tuple(self.required_dashboard_roles)
        if self.view_mode:
            return (self.view_mode,)
        return tuple(role for role, _label in DashboardAccess.DashboardRole.choices)

    def get_dashboard_access(self):
        user = self.request.user
        if user.is_superuser:
            return None
        return DashboardAccess.objects.filter(user=user, is_active=True).first()

    def get_view_mode(self):
        if self.view_mode:
            return self.view_mode
        access = self.get_dashboard_access()
        if access:
            return access.role
        return DashboardAccess.DashboardRole.FOUNDER

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        access = self.get_dashboard_access()
        return bool(access and access.role in self.get_required_dashboard_roles())

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You do not have access to this analytics dashboard.")
        return super().handle_no_permission()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["view_mode"] = self.get_view_mode()
        context["dashboard_access"] = self.get_dashboard_access()
        context["dashboard_roles"] = DashboardAccess.DashboardRole
        return context
