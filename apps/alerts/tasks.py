from typing import Any

from celery import shared_task

from apps.alerts.services.notifications import AlertNotificationService


@shared_task()
def send_alert_notifications_task(alert_ids: list[int]) -> dict[str, Any]:
    """Notify recipients about a list of newly created alerts.

    Dispatched by the ``Alert`` ``post_save`` signal when an alert is created
    with ``CRITICAL`` or ``CAUTION`` severity in the ``OPEN`` state.

    Args:
        alert_ids: List of Alert PKs to notify about.

    Returns:
        Per-channel result dict returned by ``AlertNotificationService.send``.
    """
    return AlertNotificationService(alert_ids).send()
