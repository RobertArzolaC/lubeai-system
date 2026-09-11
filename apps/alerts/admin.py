"""Admin configuration for the alerts app."""

from django.contrib import admin

from apps.alerts import models


@admin.register(models.Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin configuration for the Alert model."""

    list_display = ("category", "severity", "status", "machine", "detected_at")
    list_filter = ("severity", "status")
    search_fields = ("category", "machine__name")
    readonly_fields = ("dedup_key",)
