"""Tests for the ``apps.equipment.models`` module."""

from django.test import TestCase

from apps.equipment import factories


class FleetModelTests(TestCase):
    """Tests for the :class:`Fleet` model."""

    def test_str_returns_name(self) -> None:
        """The string representation is the fleet name."""
        fleet = factories.FleetFactory(name="North Fleet")
        self.assertEqual(str(fleet), "North Fleet")


class BranchModelTests(TestCase):
    """Tests for the :class:`Branch` model."""

    def test_str_returns_name(self) -> None:
        """The string representation is the branch name."""
        branch = factories.BranchFactory(name="Main Branch")
        self.assertEqual(str(branch), "Main Branch")


class MachineModelTests(TestCase):
    """Tests for the :class:`Machine` model."""

    def test_str_includes_serial_number(self) -> None:
        """The string representation combines name and serial number."""
        machine = factories.MachineFactory(name="Excavator", serial_number="SN-000001")
        self.assertEqual(str(machine), "Excavator (SN-000001)")

    def test_str_without_serial_number(self) -> None:
        """Without a serial number only the name is returned."""
        machine = factories.MachineFactory(name="Excavator", serial_number="")
        self.assertEqual(str(machine), "Excavator")


class ComponentTypeModelTests(TestCase):
    """Tests for the :class:`ComponentType` model."""

    def test_str_returns_name(self) -> None:
        """The string representation is the component type name."""
        component_type = factories.ComponentTypeFactory(name="Pump")
        self.assertEqual(str(component_type), "Pump")


class ComponentModelTests(TestCase):
    """Tests for the :class:`Component` model."""

    def test_str_includes_type_and_machine(self) -> None:
        """The string representation combines type and machine name."""
        machine = factories.MachineFactory(name="Compressor")
        component = factories.ComponentFactory(
            type=factories.ComponentTypeFactory(name="Motor"), machine=machine
        )
        self.assertEqual(str(component), "Motor(Compressor)")

    def test_str_without_type(self) -> None:
        """A component without type falls back to ``Unknown Type``."""
        component = factories.ComponentFactory(
            type=None, machine=factories.MachineFactory(name="Compressor")
        )
        self.assertEqual(str(component), "Unknown Type(Compressor)")
