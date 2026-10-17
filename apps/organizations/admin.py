from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.organizations import models


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin configuration for the Organization model."""

    list_display = ("name", "slug", "kind", "parent", "is_active")
    list_filter = ("kind", "is_active", "parent")
    search_fields = ("name", "slug", "code")
    readonly_fields = ("created", "modified")
    autocomplete_fields = ("parent",)
    fieldsets = (
        (
            None,
            {"fields": ("name", "slug", "code", "kind", "parent", "is_active")},
        ),
        (_("Contact"), {"fields": ("description", "phone", "email")}),
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
    )
