"""Tests for the ``apps.reports.filtersets`` module."""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.equipment import factories as equipment_factories
from apps.reports import factories, filtersets, models


class LaboratoryFilterTests(TestCase):
    """Tests for :class:`LaboratoryFilter`."""

    def setUp(self) -> None:
        self.laboratory = factories.LaboratoryFactory(name="Acme Labs", code="LAB-ACME")
        self.other = factories.LaboratoryFactory(name="Beta Labs", code="LAB-BETA")

    def test_filter_by_name(self) -> None:
        """``name_search`` matches the name."""
        filterset = filtersets.LaboratoryFilter(
            {"name_search": "Acme"}, queryset=models.Laboratory.objects.all()
        )
        self.assertIn(self.laboratory, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_filter_by_code(self) -> None:
        """``name_search`` also matches the code."""
        filterset = filtersets.LaboratoryFilter(
            {"name_search": "LAB-BETA"}, queryset=models.Laboratory.objects.all()
        )
        self.assertIn(self.other, filterset.qs)
        self.assertNotIn(self.laboratory, filterset.qs)

    def test_filter_by_is_active(self) -> None:
        """``is_active`` filters by status."""
        inactive = factories.LaboratoryFactory(is_active=False)
        filterset = filtersets.LaboratoryFilter(
            {"is_active": "False"}, queryset=models.Laboratory.objects.all()
        )
        self.assertIn(inactive, filterset.qs)
        self.assertNotIn(self.laboratory, filterset.qs)


class ReportFilterTests(TestCase):
    """Tests for :class:`ReportFilter`."""

    def setUp(self) -> None:
        self.report = factories.ReportFactory(
            lab_number="LAB-AAA", status="APPROVED", condition="NORMAL"
        )
        self.other = factories.ReportFactory(
            lab_number="LAB-BBB", status="PENDING", condition="CRITICAL"
        )

    def test_filter_by_lab_number(self) -> None:
        """``lab_number_search`` matches the lab number."""
        filterset = filtersets.ReportFilter(
            {"lab_number_search": "AAA"}, queryset=models.Report.objects.all()
        )
        self.assertIn(self.report, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_filter_by_status(self) -> None:
        """``status`` filters by report status."""
        filterset = filtersets.ReportFilter(
            {"status": "APPROVED"}, queryset=models.Report.objects.all()
        )
        self.assertIn(self.report, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_filter_by_condition(self) -> None:
        """``condition`` filters by equipment condition."""
        filterset = filtersets.ReportFilter(
            {"condition": "CRITICAL"}, queryset=models.Report.objects.all()
        )
        self.assertIn(self.other, filterset.qs)
        self.assertNotIn(self.report, filterset.qs)

    def test_filter_by_component(self) -> None:
        """``component`` filters by component."""
        filterset = filtersets.ReportFilter(
            {"component": self.report.component_id},
            queryset=models.Report.objects.all(),
        )
        self.assertIn(self.report, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)


class AnalysisThresholdFilterTests(TestCase):
    """Tests for :class:`AnalysisThresholdFilter`."""

    def setUp(self) -> None:
        self.threshold = factories.AnalysisThresholdFactory(
            parameter="iron_fe", category="wear_metals", unit="ppm"
        )

    def test_filter_by_parameter(self) -> None:
        """``parameter_search`` matches parameter or unit."""
        filterset = filtersets.AnalysisThresholdFilter(
            {"parameter_search": "iron"},
            queryset=models.AnalysisThreshold.objects.all(),
        )
        self.assertIn(self.threshold, filterset.qs)

    def test_filter_by_unit(self) -> None:
        """``parameter_search`` also matches the unit."""
        filterset = filtersets.AnalysisThresholdFilter(
            {"parameter_search": "ppm"},
            queryset=models.AnalysisThreshold.objects.all(),
        )
        self.assertIn(self.threshold, filterset.qs)

    def test_filter_by_category(self) -> None:
        """``category`` filters by category."""
        filterset = filtersets.AnalysisThresholdFilter(
            {"category": "wear_metals"},
            queryset=models.AnalysisThreshold.objects.all(),
        )
        self.assertIn(self.threshold, filterset.qs)


class ReportExportFilterTests(TestCase):
    """Tests for :class:`ReportExportFilter`."""

    def test_filter_by_date_range(self) -> None:
        """The export filter supports a sample date range."""
        in_range = factories.ReportFactory(sample_date=date(2024, 6, 15))
        out_of_range = factories.ReportFactory(sample_date=date(2023, 1, 1))
        filterset = filtersets.ReportExportFilter(
            {"start_date": "2024-01-01", "end_date": "2024-12-31"},
            queryset=models.Report.objects.all(),
        )
        self.assertIn(in_range, filterset.qs)
        self.assertNotIn(out_of_range, filterset.qs)

    def test_export_filter_accepts_component(self) -> None:
        """The export filter exposes a component relation filter."""
        self.assertIn("component", filtersets.ReportExportFilter.base_filters)
        equipment_factories.ComponentFactory()


class ComponentAnalysisFilterTests(TestCase):
    """Tests for :class:`ComponentAnalysisFilter`."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory()
        self.other_machine = equipment_factories.MachineFactory()
        self.component = equipment_factories.ComponentFactory(machine=self.machine)
        self.other_component = equipment_factories.ComponentFactory(
            machine=self.other_machine
        )

    def test_component_choices_scoped_to_machine(self) -> None:
        """Selecting a machine narrows the component choices to its own."""
        filterset = filtersets.ComponentAnalysisFilter(
            {"machine": self.machine.pk},
            queryset=models.Report.objects.all(),
        )
        choices = filterset.filters["component"].queryset
        self.assertIn(self.component, choices)
        self.assertNotIn(self.other_component, choices)

    def test_component_field_uses_forwarding_autocomplete(self) -> None:
        """The component widget forwards the machine to the autocomplete."""
        filterset = filtersets.ComponentAnalysisFilter(
            queryset=models.Report.objects.all()
        )
        widget = filterset.filters["component"].field.widget
        self.assertEqual(widget.url, reverse("apps.equipment:autocomplete_component"))
        self.assertEqual(widget.forward, ["machine"])
