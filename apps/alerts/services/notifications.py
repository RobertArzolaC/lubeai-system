"""Alert notification services.

Sends alert notification emails to active users. The email channel toggle is
read from Django Constance (``ENABLE_SEND_EMAIL``).
"""

import logging
from typing import Any

from constance import config
from django.core.mail import EmailMultiAlternatives
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from apps.alerts import models
from apps.users import models as user_models

logger = logging.getLogger(__name__)


class AlertNotificationService:
    """Dispatch alert notifications across enabled channels.

    Args:
        alert_ids: List of Alert PKs to notify about.
    """

    def __init__(self, alert_ids: list[int]) -> None:
        self.alert_ids = alert_ids

    def get_alerts(self) -> QuerySet:
        """Return the alerts for the configured IDs with related objects."""
        return models.Alert.objects.filter(id__in=self.alert_ids).select_related(
            "machine", "component", "report"
        )

    def send(self) -> dict[str, Any]:
        """Dispatch alert notifications for the supported channels.

        Returns:
            Per-channel result dict::

                {
                    "email": {"sent": int, "errors": [...]},
                }
        """
        result = self._send_email()
        logger.info("Alert notification results: email=%s", result)
        return {"email": result}

    def _send_email(self) -> dict[str, Any]:
        """Notify recipients by email, respecting ``ENABLE_SEND_EMAIL``."""
        if not config.ENABLE_SEND_EMAIL:
            logger.info("Email sending is disabled via ENABLE_SEND_EMAIL")
            return {"sent": 0, "errors": []}

        alerts = self.get_alerts()
        if not alerts.exists():
            return {"sent": 0, "errors": []}

        recipients = user_models.Account.objects.filter(
            user__is_active=True,
            is_removed=False,
        ).select_related("user")

        sent = 0
        errors: list[dict[str, Any]] = []
        for account in recipients:
            try:
                self._dispatch_email(alerts, account)
                sent += 1
            except Exception as exc:
                logger.exception("Email alert error for %s", account.user.email)
                errors.append({"email": account.user.email, "error": str(exc)})

        return {"sent": sent, "errors": errors}

    @staticmethod
    def _dispatch_email(alerts: QuerySet, account: user_models.Account) -> None:
        """Render and send the alert notification email to a single account."""
        html_content = render_to_string(
            "alerts/email/alert_notification.html", {"alerts": alerts}
        )
        text_content = strip_tags(html_content)

        email_message = EmailMultiAlternatives(
            subject="[LubeAI] Alerta: condición detectada",
            body=text_content,
            to=[account.user.email],
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)

        logger.info("Alert notification email sent to %s", account.user.email)
