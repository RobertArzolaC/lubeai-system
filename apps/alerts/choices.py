"""Choice enumerations for the alerts app."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class AlertSeverity(models.TextChoices):
    """Severity level of an alert."""

    CRITICAL = "CRITICAL", _("Critical")
    CAUTION = "CAUTION", _("Caution")
    WARNING = "WARNING", _("Warning")


class AlertStatus(models.TextChoices):
    """Lifecycle status of an alert."""

    OPEN = "OPEN", _("Open")
    ACKNOWLEDGED = "ACKNOWLEDGED", _("Acknowledged")
    RESOLVED = "RESOLVED", _("Resolved")
    DISMISSED = "DISMISSED", _("Dismissed")
