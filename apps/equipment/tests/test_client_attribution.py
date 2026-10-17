"""Tests for client attribution on branches, machines and component types."""

from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.equipment import factories as equipment_factories
from apps.equipment import filtersets, forms, models
from apps.equipment import views as equipment_views
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


def user_for(organization):
    """Return a persisted user belonging to ``organization``."""
    user = user_factories.UserFactory()
    user.organization = organization
    user.save(update_fields=["organization"])
    return user


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given equipment permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="equipment",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)


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


class ClientFilterTests(TestCase):
    """The list filters accept an organization and hide it for leaf users."""

    def setUp(self) -> None:
        """Build a lab with two final clients, each owning a branch."""
        self.lab = organization_factories.OrganizationFactory(
            slug="cf-lab", kind=choices.OrganizationKind.LAB
        )
        self.client_a = organization_factories.OrganizationFactory(
            slug="cf-a", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.client_b = organization_factories.OrganizationFactory(
            slug="cf-b", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.branch_a = equipment_factories.BranchFactory(organization=self.client_a)
        self.branch_b = equipment_factories.BranchFactory(organization=self.client_b)
        equipment_factories.MachineFactory(organization=self.client_a)
        self.user = user_for(self.lab)

    def test_branch_filter_by_organization(self) -> None:
        """Filtering by organization narrows the branches."""
        request = SimpleNamespace(user=self.user)
        filtered = filtersets.BranchFilter(
            {"organization": self.client_a.pk},
            queryset=models.Branch.objects.all(),
            request=request,
        ).qs
        self.assertEqual(list(filtered), [self.branch_a])

    def test_organization_filter_hidden_for_leaf(self) -> None:
        """A leaf user gets no organization filter."""
        request = SimpleNamespace(user=user_for(self.client_a))
        filterset = filtersets.BranchFilter(
            queryset=models.Branch.objects.all(), request=request
        )
        self.assertNotIn("organization", filterset.filters)

    def test_organization_filter_choices_are_scoped(self) -> None:
        """The choices are limited to the visible subtree."""
        request = SimpleNamespace(user=self.user)
        filterset = filtersets.MachineFilter(
            queryset=models.Machine.objects.all(), request=request
        )
        ids = set(
            filterset.filters["organization"].queryset.values_list("id", flat=True)
        )
        self.assertEqual(ids, {self.lab.id, self.client_a.id, self.client_b.id})


class ClientListContextTests(TestCase):
    """The list views expose the organization join and the show flag."""

    def setUp(self) -> None:
        """Build a lab with one final client."""
        self.lab = organization_factories.OrganizationFactory(
            slug="lc-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="lc-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )

    def test_machine_list_selects_organization(self) -> None:
        """The machine list joins the organization to avoid N+1 queries."""
        related = equipment_views.MachineListView().get_queryset().query.select_related
        self.assertIn("organization", related)

    def _show_flag(self, user) -> bool:
        """Return ``show_organization`` for ``user`` on the branch list."""
        view = equipment_views.BranchListView()
        view.request = SimpleNamespace(user=user, GET={})
        view.kwargs = {}
        view.object_list = view.get_queryset()
        return view.get_context_data()["show_organization"]

    def test_show_organization_flag(self) -> None:
        """The flag follows ``can_choose_organization``."""
        self.assertTrue(self._show_flag(user_for(self.lab)))
        self.assertFalse(self._show_flag(user_for(self.final)))


class ClientColumnRenderingTests(TestCase):
    """The Client column and filter appear for parent users only."""

    def setUp(self) -> None:
        """Build a lab owning a final client with one branch."""
        self.lab = organization_factories.OrganizationFactory(
            slug="cr-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="cr-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.branch = equipment_factories.BranchFactory(
            name="Sucursal Unica", organization=self.final
        )

    def test_parent_sees_column_and_filter(self) -> None:
        """A parent user gets the organization filter and the client name."""
        user = user_for(self.lab)
        grant_permissions(user, "view_branch")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.equipment:branch_list"))
        self.assertContains(response, 'name="organization"')
        self.assertContains(response, self.final.name)

    def test_leaf_does_not_see_column_or_filter(self) -> None:
        """A leaf user sees the plain list, without the client column."""
        user = user_for(self.final)
        grant_permissions(user, "view_branch")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.equipment:branch_list"))
        self.assertNotContains(response, 'name="organization"')

    def test_machine_list_shows_client_column(self) -> None:
        """The machine list renders the client column for a parent user."""
        equipment_factories.MachineFactory(organization=self.final)
        user = user_for(self.lab)
        grant_permissions(user, "view_machine")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.equipment:machine_list"))
        self.assertContains(response, 'name="organization"')
        self.assertContains(response, self.final.name)
