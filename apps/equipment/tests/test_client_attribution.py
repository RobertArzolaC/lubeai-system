"""Tests for client attribution on branches, machines and component types."""

from django.test import TestCase

from apps.equipment import factories as equipment_factories
from apps.equipment import forms
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


def user_for(organization):
    """Return a persisted user belonging to ``organization``."""
    user = user_factories.UserFactory()
    user.organization = organization
    user.save(update_fields=["organization"])
    return user


class OrganizationFormFieldTests(TestCase):
    """The Client field is scoped and only shown when the user can choose."""

    def setUp(self) -> None:
        """Build lab -> intermediary -> final."""
        self.lab = organization_factories.OrganizationFactory(
            slug="ff-lab", kind=choices.OrganizationKind.LAB
        )
        self.inter = organization_factories.OrganizationFactory(
            slug="ff-inter",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.lab,
        )
        self.final = organization_factories.OrganizationFactory(
            slug="ff-final", kind=choices.OrganizationKind.FINAL, parent=self.inter
        )

    def test_field_hidden_without_user(self) -> None:
        """A form built without a user has no Client field."""
        self.assertNotIn("organization", forms.ComponentTypeForm().fields)

    def test_field_hidden_for_leaf_user(self) -> None:
        """A final client cannot choose an organization."""
        form = forms.ComponentTypeForm(user=user_for(self.final))
        self.assertNotIn("organization", form.fields)

    def test_field_scoped_for_intermediary(self) -> None:
        """An intermediary only sees its subtree in the choices."""
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(user=user)
        self.assertIn("organization", form.fields)
        ids = set(form.fields["organization"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.inter.id, self.final.id})

    def test_foreign_organization_is_rejected(self) -> None:
        """A posted organization outside the subtree is invalid."""
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(
            data={"organization": self.lab.pk, "name": "X", "is_active": True},
            user=user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("organization", form.errors)

    def test_selected_organization_is_saved(self) -> None:
        """A valid selection is stored on the instance."""
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(
            data={
                "organization": self.final.pk,
                "name": "Tipo hijo",
                "is_active": True,
            },
            user=user,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save().organization_id, self.final.id)

    def test_empty_organization_keeps_current_owner(self) -> None:
        """An empty selection on update must not clear the current owner."""
        owner = organization_factories.OrganizationFactory(
            slug="ff-owner", kind=choices.OrganizationKind.FINAL
        )
        component_type = equipment_factories.ComponentTypeFactory(
            organization=owner, name="Tipo"
        )
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(
            data={"organization": "", "name": "Tipo renombrado", "is_active": True},
            instance=component_type,
            user=user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        component_type.refresh_from_db()
        self.assertEqual(component_type.organization_id, owner.id)


class MachineClientCoherenceTests(TestCase):
    """A machine's branch must belong to the selected client."""

    def setUp(self) -> None:
        """Build a lab with two final clients, each owning a branch."""
        self.lab = organization_factories.OrganizationFactory(
            slug="mc-lab", kind=choices.OrganizationKind.LAB
        )
        self.client_a = organization_factories.OrganizationFactory(
            slug="mc-a", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.client_b = organization_factories.OrganizationFactory(
            slug="mc-b", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.user = user_for(self.lab)
        self.branch_b = equipment_factories.BranchFactory(organization=self.client_b)

    def _machine_data(self, **overrides):
        """Build a valid machine payload with room for overrides."""
        data = {
            "organization": self.client_a.pk,
            "branch": "",
            "fleet": "",
            "name": "Maquina",
            "serial_number": "SN-1",
            "model": "M",
            "is_active": True,
        }
        data.update(overrides)
        return data

    def test_branch_of_another_client_is_rejected(self) -> None:
        """A branch owned by a different client invalidates the form."""
        form = forms.MachineForm(
            data=self._machine_data(branch=self.branch_b.pk), user=self.user
        )
        self.assertFalse(form.is_valid())
        self.assertIn("branch", form.errors)

    def test_organization_is_taken_from_the_branch(self) -> None:
        """Without an explicit client, the branch's client is used."""
        form = forms.MachineForm(
            data=self._machine_data(organization="", branch=self.branch_b.pk),
            user=self.user,
        )
        self.assertTrue(form.is_valid())
        machine = form.save()
        self.assertEqual(machine.organization_id, self.client_b.id)
