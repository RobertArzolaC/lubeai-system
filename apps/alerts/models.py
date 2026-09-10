"""Models for the alerts app."""

from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel

from apps.alerts import choices
from apps.core.models import BaseUserTracked
from apps.equipment.models import Component, Machine
from apps.reports import choices as report_choices
from apps.reports.models import Report


class Alert(TimeStampedModel, BaseUserTracked):
    """Alert model.

    Represents a generated alert for a monitored parameter, derived
    from an inspection report and tied to a machine/component.
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
    parameter = models.CharField(
        _("Parameter"),
        max_length=100,
        choices=report_choices.Parameter.choices,
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
    rule_type = models.CharField(
        _("Rule Type"),
        max_length=30,
        choices=choices.AlertRuleType.choices,
        default=choices.AlertRuleType.THRESHOLD,
    )
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
    sent_channels = models.JSONField(_("Sent Channels"), default=list, blank=True)
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
            models.Index(fields=["machine", "parameter", "detected_at"]),
        ]

    def __str__(self) -> str:
        """Return string representation of the alert."""
        return f"Alert {self.parameter} - {self.get_severity_display()}"
