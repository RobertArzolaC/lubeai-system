"""App configuration for the integrations app."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IntegrationsConfig(AppConfig):
    """Register the MCP tools when Django starts."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"
    verbose_name = _("Integrations")

    def ready(self) -> None:
        """Import the MCP server so its tools are registered in every process."""
        from apps.integrations.mcp import server  # noqa: F401
