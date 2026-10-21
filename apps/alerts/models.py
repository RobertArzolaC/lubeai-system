"""Models for the alerts app."""

from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel

from apps.alerts import choices, validators
from apps.core.models import BaseUserTracked, StatusHistory
from apps.equipment.models import Component, Machine
from apps.reports import choices as report_choices
from apps.reports.models import Report


class Alert(TimeStampedModel, BaseUserTracked):
    """Alert model.

    Represents a generated alert at report/sample level, derived from an
    inspection report and tied to a machine/component. The ``category``,
    ``value`` and limit fields describe the most severe parameter detected
    in the report.
    """

    machine = models.ForeignKey(
        Machine,
        verbose_name=_("Machine"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        help_text=_("Machine associated with this alert"),
    )
    component = models.ForeignKey(
        Component,
        verbose_name=_("Component"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        help_text=_("Component associated with this alert"),
    )
    report = models.ForeignKey(
        Report,
        verbose_name=_("Report"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        help_text=_("Source report of this alert"),
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name=_("Organization"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        help_text=_("Tenant/client organization that owns this alert"),
    )
    category = models.CharField(
        _("Category"),
        max_length=50,
        choices=report_choices.Category.choices,
    )
    severity = models.CharField(
        _("Severity"),
        max_length=20,
        choices=choices.AlertSeverity.choices,
        default=choices.AlertSeverity.CAUTION,
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=choices.AlertStatus.choices,
        default=choices.AlertStatus.OPEN,
        db_index=True,
    )
    value = models.FloatField(_("Value"), null=True, blank=True)
    warning_limit = models.FloatField(_("Warning Limit"), null=True, blank=True)
    critical_limit = models.FloatField(_("Critical Limit"), null=True, blank=True)
    unit = models.CharField(_("Unit"), max_length=20, blank=True, default="ppm")
    detected_at = models.DateTimeField(_("Detected At"), null=True, blank=True)
    acknowledged_at = models.DateTimeField(_("Acknowledged At"), null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Acknowledged By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
    )
    resolved_at = models.DateTimeField(_("Resolved At"), null=True, blank=True)
    dedup_key = models.CharField(
        _("Dedup Key"),
        max_length=200,
        unique=True,
        help_text=_("Idempotency key"),
    )

    class Meta:
        verbose_name = _("Alert")
        verbose_name_plural = _("Alerts")
        ordering = ("-detected_at", "-created")
        permissions: ClassVar[list[tuple[str, str]]] = [
            ("acknowledge_alert", _("Can acknowledge alert")),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["status", "severity", "detected_at"]),
            models.Index(fields=["machine", "detected_at"]),
        ]

    def __str__(self) -> str:
        """Return string representation of the alert."""
        return f"Alert {self.get_category_display()} - {self.get_severity_display()}"


def alert_attachment_upload_to(instance: "AlertStatusHistory", filename: str) -> str:
    """Return a non-guessable storage path for a status attachment.

    Args:
        instance: The history entry receiving the file.
        filename: Original uploaded filename.

    Returns:
        Relative storage path under ``alerts/attachments``.
    """
    suffix = Path(filename).suffix.lower()
    organization = instance.alert.organization_id or "unassigned"
    return f"alerts/attachments/{organization}/{uuid4().hex}{suffix}"


class AlertStatusHistory(StatusHistory):
    """Record of a status change made from the alert status modal.

    Each entry keeps the previous and new status, the optional description
    written by the acting user and an optional evidence file, so reopening or
    resolving an alert never overwrites the earlier context.
    """

    alert = models.ForeignKey(
        Alert,
        verbose_name=_("Alert"),
        on_delete=models.CASCADE,
        related_name="status_history",
        help_text=_("Alert whose status changed"),
    )
    original_filename = models.CharField(
        _("Original filename"),
        max_length=255,
        blank=True,
        help_text=_("Filename as uploaded by the user"),
    )
    attachment = models.FileField(
        _("Attachment"),
        upload_to=alert_attachment_upload_to,
        validators=[validators.validate_alert_attachment],
        blank=True,
        help_text=_("Optional evidence attached to the status change"),
    )

    class Meta:
        verbose_name = _("Alert status history")
        verbose_name_plural = _("Alert status histories")
        ordering = ("-created",)
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["alert", "-created"]),
            models.Index(fields=["created"]),
        ]

    @property
    def status_label(self) -> str:
        """Return the human-readable label of the new status."""
        return self._label(self.status)

    @property
    def previous_status_label(self) -> str:
        """Return the human-readable label of the previous status."""
        return self._label(self.previous_status)

    @property
    def attachment_filename(self) -> str:
        """Return the original filename, falling back to the stored name."""
        if self.original_filename:
            return self.original_filename
        return Path(self.attachment.name).name if self.attachment else ""

    def get_parent_filters(self) -> dict:
        """Return the filters that identify the owning alert."""
        return {"alert_id": self.alert_id}

    @classmethod
    def get_parent_kwargs(cls, instance: Alert) -> dict:
        """Return the kwargs that link a new entry to ``instance``."""
        return {"alert": instance}

    @staticmethod
    def _label(value: str) -> str:
        """Return the translated label for an alert status value."""
        try:
            return str(choices.AlertStatus(value).label)
        except ValueError:
            return value
