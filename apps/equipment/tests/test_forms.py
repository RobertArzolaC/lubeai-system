"""Tests for the ``apps.equipment.forms`` module."""

from django.test import TestCase

from apps.equipment import forms


class FleetFormTests(TestCase):
    """Tests for the :class:`FleetForm`."""

    def test_valid_with_name(self) -> None:
        """A name is enough for the form to be valid."""
        form = forms.FleetForm(data={"name": "North Fleet", "is_active": True})
        self.assertTrue(form.is_valid())

    def test_invalid_without_name(self) -> None:
        """The form requires a name."""
        form = forms.FleetForm(data={"name": "", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)


class BranchFormTests(TestCase):
    """Tests for the :class:`BranchForm`."""

    def test_valid_with_name(self) -> None:
        """A name is enough for the form to be valid."""
        form = forms.BranchForm(data={"name": "Main Branch", "is_active": True})
        self.assertTrue(form.is_valid())


class MachineFormTests(TestCase):
    """Tests for the :class:`MachineForm`."""

    def test_valid_with_required_fields(self) -> None:
        """The required machine fields are validated."""
        form = forms.MachineForm(
            data={
                "name": "Excavator",
                "serial_number": "SN-000001",
                "model": "CAT-320",
                "is_active": True,
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_without_required_fields(self) -> None:
        """Missing name, serial number or model makes the form invalid."""
        form = forms.MachineForm(data={"is_active": True})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            set(form.errors),
            {"name", "serial_number", "model"},
        )


class ComponentTypeFormTests(TestCase):
    """Tests for the :class:`ComponentTypeForm`."""

    def test_valid_with_name(self) -> None:
        """A name is enough for the form to be valid."""
        form = forms.ComponentTypeForm(
            data={"name": "Pump", "description": "Rotary pump", "is_active": True}
        )
        self.assertTrue(form.is_valid())

    def test_invalid_without_name(self) -> None:
        """The form requires a name."""
        form = forms.ComponentTypeForm(data={"name": "", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
