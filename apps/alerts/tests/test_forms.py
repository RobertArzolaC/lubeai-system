"""Tests for the ``apps.alerts.forms`` module."""

from django.test import TestCase

from apps.alerts import factories, forms
from apps.equipment import factories as equipment_factories
from apps.users import factories as user_factories


def alert_payload(alert, **overrides: object) -> dict:
    """Build a valid AlertForm payload from an existing alert."""
    data: dict = {
        "machine": alert.machine_id,
        "component": alert.component_id,
        "report": alert.report_id,
        "parameter": alert.parameter,
        "category": alert.category,
        "severity": alert.severity,
        "status": alert.status,
        "value": alert.value,
        "warning_limit": alert.warning_limit,
        "critical_limit": alert.critical_limit,
        "unit": alert.unit,
        "rule_type": alert.rule_type,
        "detected_at": alert.detected_at,
    }
    data.update(overrides)
    return data


class AlertFormTests(TestCase):
    """Tests for :class:`AlertForm`."""

    def setUp(self) -> None:
        self.user = user_factories.UserFactory()
        self.alert = factories.AlertFactory(status="OPEN")

    def test_system_fields_are_not_editable(self) -> None:
        """System-managed fields are excluded from the form."""
        form = forms.AlertForm(instance=self.alert)
        for field in ("dedup_key", "sent_channels", "created_by", "acknowledged_by"):
            with self.subTest(field=field):
                self.assertNotIn(field, form.fields)

    def test_relation_querysets_limited_to_active(self) -> None:
        """Relation fields only offer active records."""
        inactive_machine = equipment_factories.MachineFactory(is_active=False)
        form = forms.AlertForm(instance=self.alert)
        self.assertNotIn(inactive_machine, form.fields["machine"].queryset)

    def test_equal_limits_are_invalid(self) -> None:
        """Warning and critical limits must be different."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, warning_limit=50, critical_limit=50),
            instance=self.alert,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("critical_limit", form.errors)

    def test_valid_form_saves_changes(self) -> None:
        """A valid payload updates the alert fields."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, severity="CRITICAL", value=123.0),
            instance=self.alert,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.severity, "CRITICAL")
        self.assertEqual(self.alert.value, 123.0)

    def test_save_applies_acknowledgement_transition(self) -> None:
        """Saving with ACKNOWLEDGED stamps the author and timestamp."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, status="ACKNOWLEDGED"),
            instance=self.alert,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.acknowledged_by, self.user)
        self.assertIsNotNone(self.alert.acknowledged_at)

    def test_save_applies_resolution_transition(self) -> None:
        """Saving with RESOLVED stamps the resolution timestamp."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, status="RESOLVED"),
            instance=self.alert,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.alert.refresh_from_db()
        self.assertIsNotNone(self.alert.resolved_at)
