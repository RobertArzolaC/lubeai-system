"""Tests for apps.dashboard.filtersets."""

from datetime import date

from django.test import TestCase

from apps.dashboard.filtersets import DashboardFilter
from apps.equipment import factories as equipment_factories
from apps.reports import factories as reports_factories
from apps.reports import models as reports_models


class DashboardFilterTests(TestCase):
    """Filtering tests for the dashboard reports queryset."""

    def setUp(self) -> None:
        self.fleet = equipment_factories.FleetFactory(name="Flota Sur")
        self.machine = equipment_factories.MachineFactory(fleet=self.fleet)
        self.component_type = equipment_factories.ComponentTypeFactory(name="Bomba")
        self.match = reports_factories.ReportFactory(
            machine=self.machine,
            component__type=self.component_type,
            condition="NORMAL",
            sample_date=date(2023, 6, 1),
        )
        self.other = reports_factories.ReportFactory(
            condition="CRITICAL", sample_date=date(2024, 6, 1)
        )

    def test_filter_by_year(self) -> None:
        """The year filter uses the sample_date year lookup."""
        filterset = DashboardFilter({"year": 2023}, queryset=reports_models.Report.objects.all())
        self.assertIn(self.match, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_filter_by_fleet(self) -> None:
        """The fleet filter uses the machine fleet relation."""
        filterset = DashboardFilter(
            {"fleet": self.fleet.pk}, queryset=reports_models.Report.objects.all()
        )
        self.assertIn(self.match, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_filter_by_component_type(self) -> None:
        """The component type filter uses the component type relation."""
        filterset = DashboardFilter(
            {"component_type": self.component_type.pk},
            queryset=reports_models.Report.objects.all(),
        )
        self.assertIn(self.match, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_empty_filters_returns_all(self) -> None:
        """An empty filterset keeps the full queryset."""
        filterset = DashboardFilter({}, queryset=reports_models.Report.objects.all())
        self.assertEqual(filterset.qs.count(), 2)
