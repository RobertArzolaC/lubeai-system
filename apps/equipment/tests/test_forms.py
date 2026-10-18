"""Tests for the ``apps.equipment.forms`` module."""

from constance.test import override_config

from apps.core.tests.base import TenantSchemaTestCase
from apps.equipment import forms
from apps.equipment.factories import FleetFactory, MachineFactory


class FleetFormTests(TenantSchemaTestCase):
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


class BranchFormTests(TenantSchemaTestCase):
    """Tests for the :class:`BranchForm`."""

    def test_valid_with_name(self) -> None:
        """A name is enough for the form to be valid."""
        form = forms.BranchForm(data={"name": "Main Branch", "is_active": True})
        self.assertTrue(form.is_valid())


class MachineFormTests(TenantSchemaTestCase):
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

    @override_config(ENABLE_FLEET=False)
    def test_fleet_field_hidden_when_flag_disabled(self) -> None:
        """The fleet field is removed from the form when the flag is off."""
        form = forms.MachineForm()
        self.assertNotIn("fleet", form.fields)

    @override_config(ENABLE_FLEET=True)
    def test_fleet_field_present_when_flag_enabled(self) -> None:
        """The fleet field is available when the flag is on."""
        form = forms.MachineForm()
        self.assertIn("fleet", form.fields)

    @override_config(ENABLE_FLEET=False)
    def test_saving_without_fleet_keeps_existing_value(self) -> None:
        """Saving a machine with the flag off must not clear its fleet."""
        fleet = FleetFactory()
        machine = MachineFactory(fleet=fleet)
        form = forms.MachineForm(
            data={
                "name": machine.name,
                "serial_number": machine.serial_number,
                "model": machine.model,
                "is_active": True,
            },
            instance=machine,
        )
        self.assertTrue(form.is_valid())
        form.save()
        machine.refresh_from_db()
        self.assertEqual(machine.fleet, fleet)


class ComponentTypeFormTests(TenantSchemaTestCase):
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
