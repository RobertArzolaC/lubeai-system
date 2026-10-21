"""Views for the integrations app."""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView, View
from django_mcpz.oauth.models import Client

from apps.integrations.providers import provider_guides
from apps.integrations.services import MCPConnectionService


@method_decorator(never_cache, name="dispatch")
class ConnectedAppsView(LoginRequiredMixin, TemplateView):
    """Show the OAuth assistants connected by the current user."""

    template_name = "integrations/connected_apps.html"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add the MCP URL, connections and navigation context."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        resource = self.request.build_absolute_uri("/mcp")
        context.update(
            {
                "entity": _("Asistentes conectados"),
                "back_url": reverse_lazy("apps.dashboard:index"),
                "mcp_url": resource,
                "providers": provider_guides(resource),
                "connections": MCPConnectionService().connections_for_user(
                    user, resource
                ),
                "has_organization": bool(user.organization_id),
                "has_any_module": any(
                    user.has_perm(permission)
                    for permission in (
                        "equipment.view_machine",
                        "reports.view_report",
                        "alerts.view_alert",
                    )
                ),
            }
        )
        return context


class DisconnectAppView(LoginRequiredMixin, View):
    """Revoke the current user's tokens for one OAuth client."""

    http_method_names: ClassVar[list[str]] = ["post"]

    def post(self, request, *args: Any, **kwargs: Any) -> HttpResponse:
        """Disconnect the assistant and redirect back to the connection list."""
        try:
            MCPConnectionService().disconnect(request.user, kwargs["pk"])
        except Client.DoesNotExist as error:
            raise Http404(_("Asistente no encontrado.")) from error
        messages.success(request, _("Asistente desconectado correctamente."))
        return redirect("apps.integrations:connected_apps")
