"""Alert lifecycle services."""

from typing import Any

from django.utils import timezone

from apps.alerts import choices, models


class AlertService:
    """Apply consistent lifecycle transitions to :class:`Alert` instances.

    Alerts are generated automatically from inspection reports, so this
    service keeps the acknowledgement and resolution timestamps in sync when
    an alert's ``status`` is edited.
    """

    def apply_status_transition(
        self,
        alert: models.Alert,
        user: Any | None = None,
    ) -> models.Alert:
        """Sync lifecycle timestamps with the alert's current status.

        Args:
            alert: The alert being edited (its ``status`` is already set).
            user: The user performing the change, used for ``acknowledged_by``.

        Returns:
            The same alert instance with lifecycle fields updated in memory.
        """
        now = timezone.now()
        status = alert.status

        if status == choices.AlertStatus.ACKNOWLEDGED:
            if alert.acknowledged_at is None:
                alert.acknowledged_at = now
            if alert.acknowledged_by_id is None and user is not None:
                alert.acknowledged_by = user
        elif status == choices.AlertStatus.RESOLVED:
            if alert.resolved_at is None:
                alert.resolved_at = now
        elif status == choices.AlertStatus.OPEN:
            alert.acknowledged_at = None
            alert.acknowledged_by = None
            alert.resolved_at = None

        return alert
