"""Application configuration for the shared tenancy registry."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TenancyConfig(AppConfig):
    """Register the tenant registry app.

    The app lives in ``SHARED_APPS``: its models are only ever migrated into
    the ``public`` schema, so a tenant can always be resolved before the
    tenant schema is selected.
    """

    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "apps.tenancy"
    label: str = "tenancy"
    verbose_name: str = _("Tenancy")

    def ready(self) -> None:
        """Wire the tenant resolver that easy-audit's request log depends on."""
        from apps.tenancy import signals

        signals.connect()
