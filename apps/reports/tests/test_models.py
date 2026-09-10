"""Tests for the ``apps.reports.models`` module."""

from django.test import TestCase

from apps.reports import factories, models


class LaboratoryModelTests(TestCase):
    """Tests for the :class:`Laboratory` model."""

    def test_str_returns_name_and_code(self) -> None:
        """The string representation includes the name and code."""
        laboratory = factories.LaboratoryFactory(name="Acme Labs", code="LAB-001")
        self.assertEqual(str(laboratory), "Acme Labs (LAB-001)")

    def test_default_ordering_by_name(self) -> None:
        """Laboratories are ordered alphabetically by name."""
        factories.LaboratoryFactory(name="Zeta")
        factories.LaboratoryFactory(name="Alpha")
        names = list(models.Laboratory.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Alpha", "Zeta"])


class ReportModelTests(TestCase):
    """Tests for the :class:`Report` model."""

    def test_str_returns_lab_number_and_condition(self) -> None:
        """The string representation includes the lab number and condition."""
        report = factories.ReportFactory(lab_number="LAB-123", condition="CRITICAL")
        self.assertEqual(
            str(report),
            f"Report {report.lab_number} - {report.get_condition_display()}",
        )

    def test_component_name_returns_type_name(self) -> None:
        """``component_name`` returns the component type name."""
        report = factories.ReportFactory()
        self.assertEqual(report.component_name, report.component.type.name)

    def test_component_name_without_component_is_na(self) -> None:
        """``component_name`` returns ``N/A`` when there is no component."""
        report = factories.ReportFactory(component=None)
        self.assertEqual(report.component_name, "N/A")


class LabAnalysisModelTests(TestCase):
    """Tests for the computed properties of :class:`LabAnalysis`."""

    def test_total_wear_metals_sums_primary_metals(self) -> None:
        """Wear metal totals sum the six primary metals."""
        analysis = factories.LabAnalysisFactory(
            iron_fe=10,
            chromium_cr=5,
            lead_pb=1,
            copper_cu=2,
            tin_sn=3,
            aluminum_al=4,
        )
        self.assertEqual(analysis.total_wear_metals, 25)

    def test_total_contaminants_sums_contaminants(self) -> None:
        """Contaminant totals sum silicon, sodium and potassium."""
        analysis = factories.LabAnalysisFactory(
            silicon_si=5, sodium_na=4, potassium_k=1
        )
        self.assertEqual(analysis.total_contaminants, 10)

    def test_additive_depletion_pct_none_without_zinc(self) -> None:
        """Additive depletion is ``None`` when zinc is not measured."""
        analysis = factories.LabAnalysisFactory(zinc_zn=None)
        self.assertIsNone(analysis.additive_depletion_pct)

    def test_additive_depletion_pct_is_capped(self) -> None:
        """Additive depletion is capped at 100%."""
        analysis = factories.LabAnalysisFactory(zinc_zn=5000)
        self.assertEqual(analysis.additive_depletion_pct, 100.0)


class AnalysisThresholdModelTests(TestCase):
    """Tests for the :class:`AnalysisThreshold` model."""

    def test_str_for_global_threshold(self) -> None:
        """Global thresholds show ``Global`` as the component name."""
        threshold = factories.AnalysisThresholdFactory(
            component_type=None,
            category="wear_metals",
            parameter="iron_fe",
        )
        self.assertIn("Global", str(threshold))

    def test_str_for_component_type_threshold(self) -> None:
        """Component-specific thresholds show the component type name."""
        from apps.equipment import factories as equipment_factories

        component_type = equipment_factories.ComponentTypeFactory(name="Pump")
        threshold = factories.AnalysisThresholdFactory(
            component_type=component_type,
            category="wear_metals",
            parameter="iron_fe",
        )
        self.assertIn("Pump", str(threshold))
