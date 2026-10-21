"""Admin configuration for the alerts app."""

from django.contrib import admin

from apps.alerts import models


class AlertStatusHistoryInline(admin.TabularInline):
    """Read-only timeline of status changes shown on the alert page."""

    model = models.AlertStatusHistory
    extra = 0
    can_delete = False
    fields = (
        "previous_status",
        "status",
        "note",
        "attachment",
        "created_by",
        "created",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        """Status history is written only by the status modal."""
        return False


@admin.register(models.Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin configuration for the Alert model."""

    list_display = ("category", "severity", "status", "machine", "detected_at")
    list_filter = ("severity", "status")
    search_fields = ("category", "machine__name")
    readonly_fields = ("dedup_key",)
    inlines = (AlertStatusHistoryInline,)


@admin.register(models.AlertStatusHistory)
class AlertStatusHistoryAdmin(admin.ModelAdmin):
    """Admin configuration for the AlertStatusHistory model."""

    list_display = ("alert", "previous_status", "status", "created_by", "created")
    list_filter = ("status",)
    search_fields = ("alert__dedup_key", "note")
    readonly_fields = (
        "alert",
        "status",
        "previous_status",
        "note",
        "attachment",
        "created_by",
        "updated_by",
        "created",
        "modified",
    )
