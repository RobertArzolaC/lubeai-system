"""Tests for the ``apps.equipment.filtersets`` module."""

from django.test import TestCase

from apps.equipment import factories, filtersets, models


class FleetFilterTests(TestCase):
    """Tests for the :class:`filtersets.FleetFilter`."""

    def setUp(self) -> None:
        self.north = factories.FleetFactory(name="North Fleet", is_active=True)
        self.south = factories.FleetFactory(name="South Fleet", is_active=False)
        self.base_queryset = models.Fleet.objects.all()

    def test_filter_by_name(self) -> None:
        """Searching by name returns matching fleets."""
        filtered = filtersets.FleetFilter(
            {"name_search": "north"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.north])

    def test_filter_by_status(self) -> None:
        """Filtering by status narrows active/inactive fleets."""
        active = filtersets.FleetFilter(
            {"is_active": "True"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(active, [self.north])
        inactive = filtersets.FleetFilter(
            {"is_active": "False"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(inactive, [self.south])

    def test_no_filters_returns_all(self) -> None:
        """Without filters every fleet is returned."""
        self.assertEqual(
            filtersets.FleetFilter(queryset=self.base_queryset).qs.count(), 2
        )


class BranchFilterTests(TestCase):
    """Tests for the :class:`BranchFilter`."""

    def setUp(self) -> None:
        self.main = factories.BranchFactory(
            name="Main Branch", address="123 Main St", is_active=True
        )
        self.remote = factories.BranchFactory(
            name="Remote Branch", address="45 Remote Ave", is_active=False
        )
        self.base_queryset = models.Branch.objects.all()

    def test_filter_by_name(self) -> None:
        """Searching by name returns matching branches."""
        filtered = filtersets.BranchFilter(
            {"name_search": "main"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.main])

    def test_filter_by_address(self) -> None:
        """Searching by address returns matching branches."""
        filtered = filtersets.BranchFilter(
            {"name_search": "Remote Ave"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.remote])


class MachineFilterTests(TestCase):
    """Tests for the :class:`MachineFilter`."""

    def setUp(self) -> None:
        self.branch = factories.BranchFactory(is_active=True)
        self.other_branch = factories.BranchFactory(is_active=True)
        self.fleet = factories.FleetFactory(is_active=True)
        self.machine = factories.MachineFactory(
            branch=self.branch,
            fleet=self.fleet,
            name="Excavator",
            serial_number="SN-123456",
            is_active=True,
        )
        self.other_machine = factories.MachineFactory(
            branch=self.other_branch,
            name="Bulldozer",
            serial_number="SN-999999",
            is_active=False,
        )
        self.base_queryset = models.Machine.objects.all()

    def test_filter_by_name_or_serial(self) -> None:
        """Searching matches name and serial number."""
        by_name = filtersets.MachineFilter(
            {"name_search": "excav"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(by_name, [self.machine])
        by_serial = filtersets.MachineFilter(
            {"name_search": "999999"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(by_serial, [self.other_machine])

    def test_filter_by_branch(self) -> None:
        """Filtering by branch returns only that branch's machines."""
        filtered = filtersets.MachineFilter(
            {"branch": self.branch.pk}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.machine])

    def test_filter_by_fleet(self) -> None:
        """Filtering by fleet returns only that fleet's machines."""
        filtered = filtersets.MachineFilter(
            {"fleet": self.fleet.pk}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.machine])


class ComponentTypeFilterTests(TestCase):
    """Tests for the :class:`ComponentTypeFilter`."""

    def setUp(self) -> None:
        self.pump = factories.ComponentTypeFactory(
            name="Pump", description="Rotary pump", is_active=True
        )
        self.motor = factories.ComponentTypeFactory(
            name="Motor", description="Electric motor", is_active=False
        )
        self.base_queryset = models.ComponentType.objects.all()

    def test_filter_by_name(self) -> None:
        """Searching by name returns matching component types."""
        filtered = filtersets.ComponentTypeFilter(
            {"name_search": "pump"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.pump])

    def test_filter_by_description(self) -> None:
        """Searching by description returns matching component types."""
        filtered = filtersets.ComponentTypeFilter(
            {"name_search": "electric"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.motor])

    def test_filter_by_status(self) -> None:
        """Filtering by status narrows active/inactive component types."""
        active = filtersets.ComponentTypeFilter(
            {"is_active": "True"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(active, [self.pump])

    def test_no_filters_returns_all(self) -> None:
        """Without filters every component type is returned."""
        self.assertEqual(
            filtersets.ComponentTypeFilter(queryset=self.base_queryset).qs.count(), 2
        )
