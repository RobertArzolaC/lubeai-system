"""Tests for the ``apps.alerts.services`` module."""

from apps.alerts import factories
from apps.alerts.services.alert_service import AlertService
from apps.alerts.services.notifications import AlertNotificationService
from apps.alerts.tests.base import AlertTenantTestCase
from apps.users import factories as user_factories


class AlertServiceTests(AlertTenantTestCase):
    """Tests for the alert lifecycle :class:`AlertService`."""

    def setUp(self) -> None:
        super().setUp()
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


class AlertStatusChangeTests(AlertTenantTestCase):
    """Tests for :meth:`AlertService.change_status`."""

    def setUp(self) -> None:
        super().setUp()
        self.user = user_factories.UserFactory()
        self.service = AlertService()
        self.alert = factories.AlertFactory(
            status="OPEN",
            severity="CRITICAL",
            value=88.0,
            unit="ppm",
        )

    def test_change_status_records_the_previous_status_and_note(self) -> None:
        """Each submission leaves a history entry with its context."""
        history = self.service.change_status(
            self.alert,
            status="RESOLVED",
            user=self.user,
            note="Se reemplazó el filtro",
        )

        self.assertEqual(history.alert, self.alert)
        self.assertEqual(history.previous_status, "OPEN")
        self.assertEqual(history.status, "RESOLVED")
        self.assertEqual(history.note, "Se reemplazó el filtro")
        self.assertEqual(history.created_by, self.user)
        self.assertEqual(history.updated_by, self.user)

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "RESOLVED")
        self.assertIsNotNone(self.alert.resolved_at)

    def test_change_status_stamps_acknowledgement_and_author(self) -> None:
        """Acknowledging stamps the acting user and the timestamp."""
        self.service.change_status(
            self.alert,
            status="ACKNOWLEDGED",
            user=self.user,
        )

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.acknowledged_by, self.user)
        self.assertIsNotNone(self.alert.acknowledged_at)

    def test_change_status_does_not_touch_readings_or_severity(self) -> None:
        """The status endpoint only changes lifecycle data."""
        self.service.change_status(
            self.alert,
            status="RESOLVED",
            user=self.user,
        )

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.severity, "CRITICAL")
        self.assertEqual(self.alert.value, 88.0)
        self.assertEqual(self.alert.unit, "ppm")

    def test_change_status_reopen_clears_timestamps(self) -> None:
        """Reopening clears the lifecycle stamps but keeps the history."""
        self.service.change_status(
            self.alert,
            status="ACKNOWLEDGED",
            user=self.user,
        )
        self.service.change_status(self.alert, status="OPEN", user=self.user)

        self.alert.refresh_from_db()
        self.assertIsNone(self.alert.acknowledged_at)
        self.assertIsNone(self.alert.acknowledged_by)
        self.assertIsNone(self.alert.resolved_at)
        self.assertEqual(self.alert.status_history.count(), 2)


class AlertNotificationServiceTests(AlertTenantTestCase):
    """Tests for :class:`AlertNotificationService` after channel cleanup."""

    def test_send_only_reports_supported_channels(self) -> None:
        """Only the email channel is reported; unsupported channels are gone."""
        alert = factories.AlertFactory()

        result = AlertNotificationService([alert.pk]).send()

        self.assertEqual(set(result.keys()), {"email"})
        self.assertIn("sent", result["email"])
        self.assertIn("errors", result["email"])
