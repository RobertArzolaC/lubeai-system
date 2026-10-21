"""Admin configuration for the alerts app."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.alerts import models


class AttachmentLinkMixin:
    """Render the attachment through the permission-checked download view."""

    @admin.display(description=_("Attachment"))
    def attachment_link(self, obj: models.AlertStatusHistory) -> str:
        """Return a link to the scoped attachment download view.

        Args:
            obj: The history entry whose attachment is displayed.

        Returns:
            A safe HTML link, or an em dash when there is no attachment.
        """
        if not obj.attachment:
            return "—"
        url = reverse("apps.alerts:alert_attachment_download", args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            url,
            obj.attachment_filename,
        )


class AlertStatusHistoryInline(AttachmentLinkMixin, admin.TabularInline):
    """Read-only timeline of status changes shown on the alert page."""

    model = models.AlertStatusHistory
    extra = 0
    can_delete = False
    fields = (
        "previous_status",
        "status",
        "note",
        "attachment_link",
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
class AlertStatusHistoryAdmin(AttachmentLinkMixin, admin.ModelAdmin):
    """Admin configuration for the AlertStatusHistory model."""

    list_display = ("alert", "previous_status", "status", "created_by", "created")
    list_filter = ("status",)
    search_fields = ("alert__dedup_key", "note")
    fields = (
        "alert",
        "status",
        "previous_status",
        "note",
        "original_filename",
        "attachment_link",
        "created_by",
        "updated_by",
        "created",
        "modified",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        """Audit entries are created only by the status modal."""
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Audit entries are immutable evidence."""
        return False
