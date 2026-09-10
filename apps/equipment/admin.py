"""Equipment admin configuration."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.equipment import models


@admin.register(models.Branch)
class BranchAdmin(admin.ModelAdmin):
    """Admin configuration for Branch model."""

    list_display = (
        "name",
        "address",
        "city",
        "country",
        "is_active",
        "created",
        "modified",
    )
    list_filter = (
        "is_active",
        "country",
        "created",
        "modified",
    )
    search_fields = (
        "name",
        "address",
    )
    readonly_fields = (
        "created",
        "modified",
        "created_by",
        "updated_by",
    )

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "name",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            _("Location"),
            {
                "fields": (
                    "address",
                    "zip_code",
                    "country",
                    "region",
                    "subregion",
                    "city",
                )
            },
        ),
        (
            _("Audit Information"),
            {
                "fields": (
                    "created",
                    "modified",
                    "created_by",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Override save_model to set created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(models.Machine)
class MachineAdmin(admin.ModelAdmin):
    """Admin configuration for Machine model."""

    list_display = (
        "name",
        "serial_number",
        "model",
        "is_active",
        "created",
        "modified",
    )
    list_filter = (
        "is_active",
        "created",
        "modified",
    )
    search_fields = (
        "name",
        "serial_number",
        "model",
    )
    readonly_fields = (
        "created",
        "modified",
        "created_by",
        "updated_by",
    )

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "name",
                    "serial_number",
                    "model",
                    "is_active",
                )
            },
        ),
        (
            _("Audit Information"),
            {
                "fields": (
                    "created",
                    "modified",
                    "created_by",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Override save_model to set created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(models.ComponentType)
class ComponentTypeAdmin(admin.ModelAdmin):
    """Admin configuration for ComponentType model."""

    list_display = (
        "name",
        "is_active",
        "created",
        "modified",
    )
    list_filter = (
        "is_active",
        "created",
        "modified",
    )
    search_fields = (
        "name",
        "description",
    )
    readonly_fields = (
        "created",
        "modified",
        "created_by",
        "updated_by",
    )

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "name",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            _("Audit Information"),
            {
                "fields": (
                    "created",
                    "modified",
                    "created_by",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Override save_model to set created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(models.Component)
class ComponentAdmin(admin.ModelAdmin):
    """Admin configuration for Component model."""

    list_display = (
        "machine",
        "type",
        "is_active",
        "created",
    )
    list_filter = (
        "is_active",
        "type",
        "created",
    )
    search_fields = (
        "machine__name",
        "machine__serial_number",
        "type__name",
    )
    readonly_fields = (
        "created",
        "modified",
        "created_by",
        "updated_by",
    )

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "machine",
                    "type",
                    "is_active",
                )
            },
        ),
        (
            _("Audit Information"),
            {
                "fields": (
                    "created",
                    "modified",
                    "created_by",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Override save_model to set created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(models.Fleet)
class FleetAdmin(admin.ModelAdmin):
    """Admin configuration for the Fleet model."""

    list_display = ("name", "is_active")
    search_fields = ("name",)
