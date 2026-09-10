"""Tests for the ``apps.reports.forms`` module."""

from django.test import TestCase

from apps.equipment import factories as equipment_factories
from apps.reports import factories, forms, models


class LaboratoryFormTests(TestCase):
    """Tests for :class:`LaboratoryForm`."""

    def test_valid_form_saves(self) -> None:
        """A valid payload creates a laboratory."""
        form = forms.LaboratoryForm(
            data={
                "name": "Acme Labs",
                "code": "LAB-001",
                "description": "Main laboratory",
                "is_active": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        laboratory = form.save()
        self.assertEqual(laboratory.name, "Acme Labs")
        self.assertEqual(laboratory.code, "LAB-001")

    def test_code_is_required(self) -> None:
        """The unique code is required."""
        form = forms.LaboratoryForm(data={"name": "Acme", "code": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("code", form.errors)


class ReportFormTests(TestCase):
    """Tests for :class:`ReportForm`."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory()
        self.component = equipment_factories.ComponentFactory(machine=self.machine)
        self.laboratory = factories.LaboratoryFactory()

    def report_payload(self, **overrides: object) -> dict:
        """Build a valid report form payload."""
        data: dict = {
            "laboratory": self.laboratory.pk,
            "machine": self.machine.pk,
            "component": self.component.pk,
            "lab_number": "LAB-900",
            "sample_date": "2024-01-15",
            "status": "PENDING",
            "condition": "NORMAL",
            "is_active": True,
        }
        data.update(overrides)
        return data

    def test_required_fields(self) -> None:
        """Machine, component, lab number and sample date are required."""
        form = forms.ReportForm(data={})
        self.assertFalse(form.is_valid())
        for field in ("machine", "component", "lab_number", "sample_date"):
            with self.subTest(field=field):
                self.assertIn(field, form.errors)

    def test_valid_payload_creates_report(self) -> None:
        """A valid payload creates a report with the extended fields."""
        form = forms.ReportForm(
            data=self.report_payload(
                recommendations="Replace filter",
                action_required="Schedule maintenance",
                turnaround_days=5,
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        report = form.save()
        self.assertEqual(report.recommendations, "Replace filter")
        self.assertEqual(report.action_required, "Schedule maintenance")
        self.assertEqual(report.turnaround_days, 5)

    def test_querysets_are_limited_to_active_records(self) -> None:
        """Relation fields only offer active records."""
        inactive_machine = equipment_factories.MachineFactory(is_active=False)
        form = forms.ReportForm()
        self.assertNotIn(inactive_machine, form.fields["machine"].queryset)


class AnalysisThresholdFormTests(TestCase):
    """Tests for :class:`AnalysisThresholdForm`."""

    def threshold_payload(self, **overrides: object) -> dict:
        """Build a valid threshold form payload."""
        data: dict = {
            "category": "wear_metals",
            "parameter": "iron_fe",
            "warning_limit": 50,
            "critical_limit": 100,
            "unit": "ppm",
            "is_active": True,
        }
        data.update(overrides)
        return data

    def test_valid_normal_threshold(self) -> None:
        """A warning below critical is valid for normal logic."""
        form = forms.AnalysisThresholdForm(data=self.threshold_payload())
        self.assertTrue(form.is_valid(), form.errors)

    def test_warning_above_critical_is_invalid(self) -> None:
        """A warning above critical is invalid for normal logic."""
        form = forms.AnalysisThresholdForm(
            data=self.threshold_payload(warning_limit=150, critical_limit=100)
        )
        self.assertFalse(form.is_valid())

    def test_inverse_logic_requires_warning_above_critical(self) -> None:
        """For inverse logic the warning must be at or above the critical."""
        valid = forms.AnalysisThresholdForm(
            data=self.threshold_payload(
                warning_limit=100, critical_limit=50, is_inverse=True
            )
        )
        self.assertTrue(valid.is_valid(), valid.errors)

        invalid = forms.AnalysisThresholdForm(
            data=self.threshold_payload(
                warning_limit=40, critical_limit=50, is_inverse=True
            )
        )
        self.assertFalse(invalid.is_valid())

    def test_component_type_queryset_limited_to_active(self) -> None:
        """The component type choices only include active records."""
        inactive = equipment_factories.ComponentTypeFactory(is_active=False)
        form = forms.AnalysisThresholdForm()
        self.assertNotIn(inactive, form.fields["component_type"].queryset)

    def test_save_persists_threshold(self) -> None:
        """A valid form persists an :class:`AnalysisThreshold`."""
        form = forms.AnalysisThresholdForm(data=self.threshold_payload())
        self.assertTrue(form.is_valid(), form.errors)
        threshold = form.save()
        self.assertIsInstance(threshold, models.AnalysisThreshold)
