"""Tests for the ``apps.alerts.forms`` module."""

from apps.alerts import factories, forms
from apps.alerts.tests.base import AlertTenantTestCase
from apps.equipment import factories as equipment_factories
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.reports import factories as report_factories
from apps.users import factories as user_factories


def alert_payload(alert, **overrides: object) -> dict:
    """Build a valid AlertForm payload from an existing alert."""
    data: dict = {
        "machine": alert.machine_id,
        "component": alert.component_id,
        "report": alert.report_id,
        "category": alert.category,
        "severity": alert.severity,
        "status": alert.status,
        "value": alert.value,
        "warning_limit": alert.warning_limit,
        "critical_limit": alert.critical_limit,
        "unit": alert.unit,
        "detected_at": alert.detected_at,
    }
    data.update(overrides)
    return data


class AlertFormScopingTests(AlertTenantTestCase):
    """Alert relation choices stay inside the actor's organization tree."""

    def setUp(self) -> None:
        """Build one visible organization and one unrelated tenant."""
        super().setUp()
        self.org = organization_factories.OrganizationFactory(
            slug="alert-form-own", kind=choices.OrganizationKind.FINAL
        )
        self.other = organization_factories.OrganizationFactory(
            slug="alert-form-other", kind=choices.OrganizationKind.FINAL
        )
        self.user = user_factories.UserFactory()
        self.user.organization = self.org
        self.user.save(update_fields=["organization"])
        foreign_machine = equipment_factories.MachineFactory(organization=self.other)
        foreign_component = equipment_factories.ComponentFactory(machine=foreign_machine)
        self.foreign_report = report_factories.ReportFactory(
            machine=foreign_machine, component=foreign_component
        )

    def test_report_choices_exclude_other_organizations(self) -> None:
        """The report dropdown does not expose reports from other tenants."""
        form = forms.AlertForm(user=self.user)
        self.assertNotIn(self.foreign_report, form.fields["report"].queryset)


class AlertFormTests(AlertTenantTestCase):
    """Tests for :class:`AlertForm`."""

    def setUp(self) -> None:
        super().setUp()
        self.user = user_factories.UserFactory()
        self.alert = factories.AlertFactory(status="OPEN")

    def test_system_fields_are_not_editable(self) -> None:
        """System-managed fields are excluded from the form."""
        form = forms.AlertForm(instance=self.alert)
        for field in (
            "dedup_key",
            "parameter",
            "rule_type",
            "sent_channels",
            "created_by",
            "acknowledged_by",
        ):
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
