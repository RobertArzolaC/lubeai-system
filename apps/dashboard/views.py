"""Views for the dashboard app."""

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.dashboard import filtersets
from apps.dashboard.services import DashboardFilters, DashboardService


class DashboardView(LoginRequiredMixin, TemplateView):
    """Render the oil analysis dashboard shell.

    The heavy payload is cached at the service layer (keyed by filters); the
    response itself is not cached so no per-user cache entries are created.
    """

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add the initial payload and the available filter options."""
        context = super().get_context_data(**kwargs)
        service = DashboardService()
        context["dashboard_data"] = service.build_context()
        context["filter_options"] = service.get_filter_options()
        return context


class DashboardDataView(LoginRequiredMixin, View):
    """Return the dashboard payload as JSON for AJAX updates."""

    def get(self, request, *args: Any, **kwargs: Any) -> JsonResponse:
        """Apply the request filters and return the JSON payload."""
        filterset = filtersets.DashboardFilter(request.GET)
        if not filterset.is_valid():
            return JsonResponse(
                {"detail": _("Invalid filters")},
                status=400,
            )
        cleaned = filterset.form.cleaned_data
        filters = DashboardFilters(
            year=cleaned.get("year"),
            fleet_id=cleaned["fleet"].pk if cleaned.get("fleet") else None,
            machine_id=cleaned["machine"].pk if cleaned.get("machine") else None,
            component_type_id=(
                cleaned["component_type"].pk if cleaned.get("component_type") else None
            ),
        )
        return JsonResponse(DashboardService(filters).build_context())
