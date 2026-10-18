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
from django.utils.translation import gettext_lazy as _

from apps.alerts import models
from apps.organizations import models as organization_models
from apps.organizations import scoping
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
            "machine", "component", "report", "organization"
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
        """Notify recipients by email, respecting ``ENABLE_SEND_EMAIL``.

        Recipients are the active users that have ``alerts.view_alert`` and
        whose organization can see the alert (the alert's organization or one
        of its ancestors). This keeps notifications inside the owning tenant;
        users of other tenants are never notified.
        """
        if not config.ENABLE_SEND_EMAIL:
            logger.info("Email sending is disabled via ENABLE_SEND_EMAIL")
            return {"sent": 0, "errors": []}

        alerts = self.get_alerts()
        if not alerts.exists():
            return {"sent": 0, "errors": []}

        alert_organization_ids = {
            organization_id
            for organization_id in alerts.values_list("organization_id", flat=True)
            if organization_id is not None
        }
        if not alert_organization_ids:
            return {"sent": 0, "errors": []}

        recipients = user_models.User.objects.filter(
            is_active=True,
            organization_id__in=self._recipient_organization_ids(
                alert_organization_ids
            ),
        ).select_related("organization")

        sent = 0
        errors: list[dict[str, Any]] = []
        for user in recipients:
            if not user.has_perm("alerts.view_alert"):
                continue

            visible_ids = scoping.user_visible_organization_ids(user)
            visible_alerts = (
                alerts
                if visible_ids is None
                else alerts.filter(organization_id__in=visible_ids)
            )
            if not visible_alerts.exists():
                continue

            try:
                self._dispatch_email(visible_alerts, user)
                sent += 1
            except Exception as exc:
                logger.exception("Email alert error for %s", user.email)
                errors.append({"email": user.email, "error": str(exc)})

        return {"sent": sent, "errors": errors}

    @staticmethod
    def _recipient_organization_ids(alert_organization_ids: set[int]) -> set[int]:
        """Return the organizations that may receive these alerts.

        For every alert organization, that organization plus its ancestors
        (the users who can see it). Never leaves the owning tenant.
        """
        organizations = organization_models.Organization.objects.filter(
            id__in=alert_organization_ids
        )
        recipient_ids: set[int] = set()
        for organization in organizations:
            recipient_ids.add(organization.id)
            recipient_ids.update(ancestor.id for ancestor in organization.ancestors())
        return recipient_ids

    @staticmethod
    def _dispatch_email(alerts: QuerySet, user: user_models.User) -> None:
        """Render and send the alert notification email to a single user."""
        html_content = render_to_string(
            "alerts/email/alert_notification.html", {"alerts": alerts}
        )
        text_content = strip_tags(html_content)

        first_alert = alerts.first()
        brand = (
            first_alert.organization.name
            if first_alert and first_alert.organization
            else "MARCO"
        )
        email_message = EmailMultiAlternatives(
            subject=_("[%(brand)s] Alerta: condición detectada") % {"brand": brand},
            body=text_content,
            to=[user.email],
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)

        logger.info("Alert notification email sent to %s", user.email)
