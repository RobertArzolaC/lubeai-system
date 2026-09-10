"""Admin configuration for the alerts app."""

from django.contrib import admin

from apps.alerts import models


@admin.register(models.Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin configuration for the Alert model."""

    list_display = ("parameter", "severity", "status", "machine", "detected_at")
    list_filter = ("severity", "status", "rule_type")
    search_fields = ("parameter", "machine__name")
    readonly_fields = ("dedup_key",)
