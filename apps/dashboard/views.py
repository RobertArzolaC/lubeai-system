"""Views for the dashboard app."""

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.dashboard import filtersets
from apps.dashboard.services import DashboardFilters, DashboardService
from apps.organizations import scoping
from apps.users import models as user_models

CLIENT_ADMIN_PERMISSIONS = (
    "organizations.view_organization",
    "users.view_user",
    "users.view_role",
)


class DashboardView(LoginRequiredMixin, TemplateView):
    """Render the oil analysis dashboard shell.

    The heavy payload is cached at the service layer (keyed by filters); the
    response itself is not cached so no per-user cache entries are created.
    """

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add the initial payload, the filter options and client counts."""
        context = super().get_context_data(**kwargs)
        organization_ids = scoping.user_visible_organization_ids(self.request.user)
        service = DashboardService(organization_ids=organization_ids)
        context["dashboard_data"] = service.build_context()
        context["filter_options"] = service.get_filter_options(organization_ids)
        context["filter_form"] = filtersets.DashboardFilter(request=self.request).form
        context.update(self._client_administration(self.request.user))
        return context

    def _client_administration(self, user) -> dict:
        """Return the client-administration flag and scoped counts.

        Args:
            user: The request user.

        Returns:
            Context with ``show_client_administration`` and ``client_counts``.
        """
        show = any(user.has_perm(permission) for permission in CLIENT_ADMIN_PERMISSIONS)
        if not show:
            return {
                "show_client_administration": False,
                "client_counts": {"organizations": 0, "users": 0, "roles": 0},
            }
        visible = scoping.visible_organizations(user)
        return {
            "show_client_administration": True,
            "client_counts": {
                "organizations": visible.count(),
                "users": user_models.User.objects.filter(
                    organization__in=visible
                ).count(),
                "roles": user_models.Role.objects.filter(
                    organization__in=visible
                ).count(),
            },
        }


class DashboardDataView(LoginRequiredMixin, View):
    """Return the dashboard payload as JSON for AJAX updates."""

    def get(self, request, *args: Any, **kwargs: Any) -> JsonResponse:
        """Apply the request filters and return the JSON payload."""
        filterset = filtersets.DashboardFilter(request.GET, request=request)
        if not filterset.is_valid():
            return JsonResponse(
                {"detail": _("Invalid filters")},
                status=400,
            )
        cleaned = filterset.form.cleaned_data
        filters = DashboardFilters(
            search=cleaned.get("search") or None,
            year=cleaned.get("year"),
            fleet_id=cleaned["fleet"].pk if cleaned.get("fleet") else None,
            machine_id=cleaned["machine"].pk if cleaned.get("machine") else None,
            component_id=(
                cleaned["component"].pk if cleaned.get("component") else None
            ),
        )
        organization_ids = scoping.user_visible_organization_ids(request.user)
        return JsonResponse(
            DashboardService(filters, organization_ids=organization_ids).build_context()
        )
