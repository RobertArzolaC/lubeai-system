"""Alert lifecycle services."""

from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.alerts import choices, models, validators


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

    @transaction.atomic
    def change_status(
        self,
        alert: models.Alert,
        *,
        status: str,
        user: Any,
        note: str = "",
        attachment: UploadedFile | None = None,
    ) -> models.AlertStatusHistory:
        """Apply a status change and record its history entry.

        Args:
            alert: The alert being updated.
            status: The new lifecycle status.
            user: The user performing the change.
            note: Optional description written in the status modal.
            attachment: Optional evidence file uploaded from the status modal.

        Returns:
            The history entry created for this change.

        Raises:
            ValueError: If ``status`` is not a valid alert status.
            ValidationError: If ``attachment`` does not pass the file rules.
        """
        if status not in choices.AlertStatus.values:
            raise ValueError("Invalid alert status.")
        if attachment is not None:
            validators.validate_alert_attachment(attachment)

        previous_status = alert.status
        alert.status = status
        self.apply_status_transition(alert, user)
        alert.updated_by = user
        alert.save(
            update_fields=[
                "status",
                "acknowledged_at",
                "acknowledged_by",
                "resolved_at",
                "updated_by",
                "modified",
            ]
        )
        return self.record_history(
            alert,
            previous_status=previous_status,
            status=status,
            user=user,
            note=note,
            attachment=attachment,
        )

    def record_history(
        self,
        alert: models.Alert,
        *,
        previous_status: str,
        status: str,
        user: Any,
        note: str = "",
        attachment: UploadedFile | None = None,
    ) -> models.AlertStatusHistory:
        """Create the audit entry for a status change.

        Args:
            alert: The alert whose status changed.
            previous_status: Status before the change.
            status: Status after the change.
            user: The user performing the change.
            note: Optional description written by the user.
            attachment: Optional evidence file uploaded by the user.

        Returns:
            The created history entry.
        """
        return models.AlertStatusHistory.objects.create(
            alert=alert,
            status=status,
            previous_status=previous_status,
            note=note,
            original_filename=Path(attachment.name).name if attachment else "",
            attachment=attachment,
            created_by=user,
            updated_by=user,
        )
