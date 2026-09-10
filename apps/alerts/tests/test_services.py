"""Tests for the ``apps.alerts.services`` module."""

from django.test import TestCase

from apps.alerts import factories
from apps.alerts.services.alert_service import AlertService
from apps.alerts.services.notifications import AlertNotificationService
from apps.users import factories as user_factories


class AlertServiceTests(TestCase):
    """Tests for the alert lifecycle :class:`AlertService`."""

    def setUp(self) -> None:
        self.user = user_factories.UserFactory()
        self.service = AlertService()

    def test_acknowledge_stamps_author_and_timestamp(self) -> None:
        """Moving an alert to ACKNOWLEDGED records the author and time."""
        alert = factories.AlertFactory(status="OPEN")

        alert.status = "ACKNOWLEDGED"
        self.service.apply_status_transition(alert, self.user)
        alert.save()

        alert.refresh_from_db()
        self.assertEqual(alert.status, "ACKNOWLEDGED")
        self.assertEqual(alert.acknowledged_by, self.user)
        self.assertIsNotNone(alert.acknowledged_at)

    def test_resolve_stamps_resolved_at(self) -> None:
        """Moving an alert to RESOLVED records the resolution time."""
        alert = factories.AlertFactory(status="ACKNOWLEDGED")

        alert.status = "RESOLVED"
        self.service.apply_status_transition(alert, self.user)
        alert.save()

        alert.refresh_from_db()
        self.assertEqual(alert.status, "RESOLVED")
        self.assertIsNotNone(alert.resolved_at)

    def test_reopen_clears_lifecycle_timestamps(self) -> None:
        """Re-opening an alert clears acknowledgement and resolution data."""
        alert = factories.AlertFactory(
            status="ACKNOWLEDGED",
            acknowledged_by=self.user,
        )

        alert.status = "OPEN"
        self.service.apply_status_transition(alert, self.user)
        alert.save()

        alert.refresh_from_db()
        self.assertIsNone(alert.acknowledged_at)
        self.assertIsNone(alert.acknowledged_by)
        self.assertIsNone(alert.resolved_at)

    def test_dismissed_keeps_lifecycle_timestamps(self) -> None:
        """DISMISSED does not stamp acknowledgement or resolution data."""
        alert = factories.AlertFactory(status="OPEN")

        alert.status = "DISMISSED"
        self.service.apply_status_transition(alert, self.user)
        alert.save()

        alert.refresh_from_db()
        self.assertIsNone(alert.resolved_at)


class AlertNotificationServiceTests(TestCase):
    """Tests for :class:`AlertNotificationService` after channel cleanup."""

    def test_send_only_reports_supported_channels(self) -> None:
        """Only the email channel is reported; unsupported channels are gone."""
        alert = factories.AlertFactory()

        result = AlertNotificationService([alert.pk]).send()

        self.assertEqual(set(result.keys()), {"email"})
        self.assertIn("sent", result["email"])
        self.assertIn("errors", result["email"])
