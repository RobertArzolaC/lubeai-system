"""Tests for apps.dashboard.filtersets."""

from datetime import date

from apps.core.tests.base import TenantSchemaTestCase
from apps.dashboard.filtersets import DashboardFilter
from apps.equipment import factories as equipment_factories
from apps.reports import factories as reports_factories
from apps.reports import models as reports_models


class DashboardFilterTests(TenantSchemaTestCase):
    """Filtering tests for the dashboard reports queryset."""

    def setUp(self) -> None:
        super().setUp()
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
        filterset = DashboardFilter(
            {"year": 2023}, queryset=reports_models.Report.objects.all()
        )
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

    def test_filter_by_lab_number(self) -> None:
        """The search matches the report's identifiers."""
        self.match.lab_number = "INFORME-UNICO"
        self.match.save(update_fields=["lab_number"])

        filterset = DashboardFilter(
            {"search": "unico"}, queryset=reports_models.Report.objects.all()
        )
        self.assertEqual(list(filterset.qs), [self.match])

    def test_filter_by_machine_name(self) -> None:
        """The search matches the machine's name."""
        self.machine.name = "Remolcador Zafiro"
        self.machine.save(update_fields=["name"])
        self.other.machine.name = "Buque Gris"
        self.other.machine.save(update_fields=["name"])

        filterset = DashboardFilter(
            {"search": "zafiro"}, queryset=reports_models.Report.objects.all()
        )
        self.assertEqual(list(filterset.qs), [self.match])

    def test_filter_by_component_type_name(self) -> None:
        """The search reaches the component type through the component."""
        self.other.component.type.name = "Compresor"
        self.other.component.type.save(update_fields=["name"])

        filterset = DashboardFilter(
            {"search": "bomba"}, queryset=reports_models.Report.objects.all()
        )
        self.assertEqual(list(filterset.qs), [self.match])

    def test_search_matches_nothing(self) -> None:
        """A search with no match narrows the queryset to zero rows."""
        filterset = DashboardFilter(
            {"search": "sin-coincidencias"}, queryset=reports_models.Report.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 0)
