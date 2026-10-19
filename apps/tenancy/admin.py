"""Admin registration for the shared tenancy registry."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_tenants.admin import TenantAdminMixin

from apps.tenancy import models, services


@admin.register(models.Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    """Admin for tenants, guarding edits outside the tenant's own schema.

    ``TenantAdminMixin`` only offers the save/delete buttons while the current
    schema is the tenant itself or ``public``, which is exactly where django
    tenants allows a tenant row to be written.
    """

    list_display: tuple[str, ...] = ("name", "slug", "kind", "is_active")
    list_filter: tuple[str, ...] = ("kind", "is_active")
    search_fields: tuple[str, ...] = ("name", "slug")
    readonly_fields: tuple[str, ...] = ("schema_name", "usage_summary")
    fieldsets: tuple[tuple[str | None, dict[str, tuple[str, ...]]], ...] = (
        (
            None,
            {"fields": ("name", "slug", "schema_name", "kind", "is_active")},
        ),
        (
            _("Branding"),
            {
                "fields": (
                    "logo",
                    "primary_color",
                    "chart_primary",
                    "chart_success",
                    "chart_warning",
                    "chart_danger",
                    "chart_info",
                    "chart_dark",
                )
            },
        ),
        (_("Capabilities"), {"fields": ("capabilities",)}),
        (_("Usage"), {"fields": ("usage_summary",)}),
    )

    @admin.display(description=_("Consumption"))
    def usage_summary(self, obj: models.Tenant) -> str:
        """Render the tenant's measured usage for the admin change page.

        Args:
            obj: The tenant being edited.

        Returns:
            A one-line summary with the schema size and the billable rows.
        """
        if obj.pk is None:
            return "-"
        usage = services.TenantService.consumption(obj)
        return f"{usage['bytes']} bytes · {usage['rows']} rows"
