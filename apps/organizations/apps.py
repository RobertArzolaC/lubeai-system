from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OrganizationsConfig(AppConfig):
    """Organizations application configuration."""

    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "apps.organizations"
    verbose_name: str = _("Organizations Management")
