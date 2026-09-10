"""Signal handlers for the alerts app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.alerts.models import Alert
from apps.alerts.services.alert_generator import AlertGeneratorService
from apps.alerts.tasks import send_alert_notifications_task
from apps.reports.models import LabAnalysis

_generator = AlertGeneratorService()

# Severities that trigger a notification when an alert is created.
_NOTIFY_SEVERITIES = ("CRITICAL", "CAUTION")


@receiver(
    post_save, sender=LabAnalysis, dispatch_uid="apps.alerts.labanalysis_post_save"
)
def ensure_alerts_for_report(sender, instance: LabAnalysis, **kwargs) -> None:
    """Generate alerts for a report when its LabAnalysis is created/updated.

    Args:
        sender: The model class sending the signal (LabAnalysis).
        instance: The LabAnalysis instance that was saved.
        **kwargs: Additional signal keyword arguments (ignored).
    """
    report = instance.report
    if report is None:
        return
    _generator.generate_for_report(report)


@receiver(post_save, sender=Alert, dispatch_uid="apps.alerts.alert_post_save")
def notify_alert_created(sender, instance: Alert, created: bool, **kwargs) -> None:
    """Dispatch alert notifications when a notifiable alert is created.

    Fires only for newly created alerts whose severity is CRITICAL or CAUTION
    and whose status is OPEN. Updates (e.g. severity re-evaluation) and
    resolved/dismissed alerts are intentionally ignored to avoid duplicate
    notifications.

    Args:
        sender: The model class sending the signal (Alert).
        instance: The Alert instance that was saved.
        created: Whether the Alert was created (as opposed to updated).
        **kwargs: Additional signal keyword arguments (ignored).
    """
    if not created:
        return
    if instance.severity not in _NOTIFY_SEVERITIES:
        return
    if instance.status != "OPEN":
        return
    send_alert_notifications_task.delay([instance.id])
