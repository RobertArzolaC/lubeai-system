"""App configuration for the dashboard app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DashboardConfig(AppConfig):
    """App configuration for the dashboard module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    verbose_name = _("Dashboard")

    def ready(self) -> None:
        """Import signal handlers when the app is ready."""
        import apps.dashboard.signals  # noqa: F401
