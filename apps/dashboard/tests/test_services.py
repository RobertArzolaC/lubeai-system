"""Tests for apps.dashboard.services.dashboard_service."""

from datetime import date

from django.test import TestCase

from apps.alerts import factories as alerts_factories
from apps.dashboard.services.dashboard_service import (
    DashboardFilters,
    DashboardService,
)
from apps.equipment import factories as equipment_factories
from apps.reports import factories as reports_factories


class DashboardServiceKPITests(TestCase):
    """KPI aggregation tests."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory(name="Buque Uno")
        self.normal = reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 3, 1)
        )
        self.caution = reports_factories.ReportFactory(
            machine=self.machine, condition="CAUTION", sample_date=date(2024, 4, 1)
        )
        self.critical = reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 5, 1)
        )

    def test_kpis_counts_by_condition(self) -> None:
        """KPIs count totals per condition and compute the rate."""
        kpis = DashboardService().get_kpis()
        self.assertEqual(kpis["total"], 3)
        self.assertEqual(kpis["normal"], 1)
        self.assertEqual(kpis["caution"], 1)
        self.assertEqual(kpis["critical"], 1)
        self.assertEqual(kpis["non_conformance_rate"], 66.7)

    def test_kpis_empty_dataset(self) -> None:
        """An empty dataset returns zeros without dividing by zero."""
        kpis = DashboardService(DashboardFilters(year=1999)).get_kpis()
        self.assertEqual(kpis["total"], 0)
        self.assertEqual(kpis["non_conformance_rate"], 0.0)

    def test_condition_distribution(self) -> None:
        """Condition distribution returns one key per condition."""
        distribution = DashboardService().get_condition_distribution()
        self.assertEqual(distribution, {"NORMAL": 1, "CAUTION": 1, "CRITICAL": 1})


class DashboardServiceSeriesTests(TestCase):
    """Monthly series and grouping tests."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory(name="Buque Dos")
        self.other_machine = equipment_factories.MachineFactory(name="Buque Tres")
        reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 1, 10)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="CAUTION", sample_date=date(2024, 1, 20)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 2, 5)
        )
        alerts_factories.AlertFactory(
            report=None,
            component=None,
            machine=self.machine,
            severity="CRITICAL",
            detected_at=None,
        )

    def test_samples_by_month(self) -> None:
        """Samples are bucketed by month with alert/caution splits."""
        data = DashboardService().get_samples_by_month()
        self.assertEqual(data["categories"], ["2024-01", "2024-02"])
        self.assertEqual(data["total"], [2, 1])
        self.assertEqual(data["alerts"], [1, 0])
        self.assertEqual(data["cautions"], [1, 0])

    def test_alerts_by_fleet(self) -> None:
        """Alerts are grouped by machine fleet name, sorted desc."""
        data = DashboardService().get_alerts_by_fleet()
        self.assertEqual(data["values"], [1])
        self.assertEqual(data["categories"], [self.machine.fleet.name])

    def test_alerts_over_time_uses_detected_at(self) -> None:
        """Alerts with detected_at are bucketed; null detected_at is ignored."""
        data = DashboardService().get_alerts_over_time()
        self.assertEqual(data["categories"], [])
        self.assertEqual(data["alerts"], [])
        self.assertEqual(data["cautions"], [])


class DashboardServiceFilterTests(TestCase):
    """Filtering behaviour tests."""

    def setUp(self) -> None:
        self.fleet = equipment_factories.FleetFactory(name="Flota Sur")
        self.other_fleet = equipment_factories.FleetFactory(name="Flota Norte")
        self.machine = equipment_factories.MachineFactory(fleet=self.fleet)
        self.other_machine = equipment_factories.MachineFactory(fleet=self.other_fleet)
        self.component_type = equipment_factories.ComponentTypeFactory(name="Bomba")
        reports_factories.ReportFactory(
            machine=self.machine,
            component__type=self.component_type,
            condition="NORMAL",
            sample_date=date(2023, 6, 1),
        )
        reports_factories.ReportFactory(
            machine=self.other_machine, condition="CRITICAL", sample_date=date(2024, 6, 1)
        )

    def test_filter_by_year(self) -> None:
        """Filtering by year narrows the report queryset."""
        service = DashboardService(DashboardFilters(year=2023))
        self.assertEqual(service.get_kpis()["total"], 1)

    def test_filter_by_fleet(self) -> None:
        """Filtering by fleet narrows the report queryset."""
        service = DashboardService(DashboardFilters(fleet_id=self.fleet.pk))
        self.assertEqual(service.get_kpis()["total"], 1)

    def test_filter_by_component_type(self) -> None:
        """Filtering by component type narrows the report queryset."""
        service = DashboardService(DashboardFilters(component_type_id=self.component_type.pk))
        self.assertEqual(service.get_kpis()["total"], 1)


class DashboardServiceISOTests(TestCase):
    """ISO 4406 parsing and classification tests."""

    def setUp(self) -> None:
        self.report_ok = reports_factories.ReportFactory(condition="NORMAL")
        reports_factories.LabAnalysisFactory(
            report=self.report_ok, particle_count_iso="20/18/15"
        )
        self.report_bad = reports_factories.ReportFactory(condition="CRITICAL")
        reports_factories.LabAnalysisFactory(
            report=self.report_bad, particle_count_iso="23/21/18"
        )

    def test_iso_distribution_and_status(self) -> None:
        """ISO codes are counted and classified against the target."""
        data = DashboardService().get_iso4406_distribution()
        self.assertEqual(data["categories"], ["20/18/15", "23/21/18"])
        self.assertEqual(data["values"], [1, 1])
        self.assertEqual(data["status"], ["normal", "critical"])

    def test_iso_invalid_code_is_ignored_or_normal(self) -> None:
        """An unparseable code is treated as normal and does not crash."""
        self.assertTrue(DashboardService._iso_is_within_target("bad-code"))


class DashboardServiceAuxTests(TestCase):
    """Range, recent reports and filter options tests."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory(name="Buque Cuatro")
        reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 1, 1)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 12, 31)
        )

    def test_range(self) -> None:
        """The range exposes the min and max sample dates."""
        data = DashboardService().get_range()
        self.assertEqual(data, {"min": "2024-01-01", "max": "2024-12-31"})

    def test_recent_reports_serialisable(self) -> None:
        """Recent reports expose display values and are JSON friendly."""
        rows = DashboardService().get_recent_reports()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["machine"], "Buque Cuatro")
        self.assertIn("condition_display", rows[0])

    def test_filter_options(self) -> None:
        """Filter options expose years, fleets, machines and component types."""
        options = DashboardService.get_filter_options()
        self.assertIn(2024, options["years"])
        self.assertTrue(options["fleets"])
