"""App configuration for the alerts app."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AlertsConfig(AppConfig):
    """App configuration for the alerts module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.alerts"
    verbose_name = _("Alerts")

    def ready(self) -> None:
        """Import signal handlers when the app is ready."""
        import apps.alerts.signals  # noqa: F401
