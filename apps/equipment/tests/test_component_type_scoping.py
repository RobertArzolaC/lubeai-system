"""Tests for organization scoping on component types."""

from types import SimpleNamespace

from django.test import TestCase

from apps.core.mixins.forms import UserStampMixin
from apps.equipment import factories as equipment_factories
from apps.equipment import models as equipment_models
from apps.equipment import views as equipment_views
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


class ComponentTypeScopingTests(TestCase):
    """Component types are visible only within the user's subtree."""

    def setUp(self) -> None:
        """Build a tree where each organization owns a distinct type."""
        self.marco = organization_factories.OrganizationFactory(
            slug="ct-marco", kind=choices.OrganizationKind.LAB
        )
        self.intermediary = organization_factories.OrganizationFactory(
            slug="ct-inter",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.marco,
        )
        self.final_a = organization_factories.OrganizationFactory(
            slug="ct-final-a", kind=choices.OrganizationKind.FINAL, parent=self.intermediary
        )
        self.final_b = organization_factories.OrganizationFactory(
            slug="ct-final-b", kind=choices.OrganizationKind.FINAL, parent=self.marco
        )
        self.type_marco = equipment_factories.ComponentTypeFactory(
            organization=self.marco, name="Tipo MARCO"
        )
        self.type_inter = equipment_factories.ComponentTypeFactory(
            organization=self.intermediary, name="Tipo Inter"
        )
        self.type_final_a = equipment_factories.ComponentTypeFactory(
            organization=self.final_a, name="Tipo Final A"
        )
        self.type_final_b = equipment_factories.ComponentTypeFactory(
            organization=self.final_b, name="Tipo Final B"
        )

    def _user_for(self, organization):
        """Return a persisted user belonging to ``organization``."""
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        return user

    def _visible_type_ids(self, user):
        """Return the component type ids the list view would expose."""
        view = equipment_views.ComponentTypeListView()
        view.request = SimpleNamespace(user=user)
        return set(view.get_queryset().values_list("id", flat=True))

    def test_final_client_sees_only_own_types(self) -> None:
        """A final client sees only the types owned by its organization."""
        user = self._user_for(self.final_a)
        self.assertEqual(self._visible_type_ids(user), {self.type_final_a.id})

    def test_intermediary_sees_own_and_descendants(self) -> None:
        """An intermediary sees its own types and its final clients'."""
        user = self._user_for(self.intermediary)
        self.assertEqual(
            self._visible_type_ids(user),
            {self.type_inter.id, self.type_final_a.id},
        )

    def test_types_of_other_branches_are_hidden(self) -> None:
        """A branch never sees a sibling branch's types."""
        user = self._user_for(self.final_a)
        ids = self._visible_type_ids(user)
        self.assertNotIn(self.type_final_b.id, ids)
        self.assertNotIn(self.type_marco.id, ids)

    def test_superuser_sees_all_types(self) -> None:
        """A superuser sees every component type."""
        superuser = user_factories.UserFactory(is_superuser=True)
        ids = self._visible_type_ids(superuser)
        self.assertEqual(
            ids,
            {
                self.type_marco.id,
                self.type_inter.id,
                self.type_final_a.id,
                self.type_final_b.id,
            },
        )

    def test_created_type_inherits_user_organization(self) -> None:
        """A component type created through the UI belongs to the creator's org."""
        user = self._user_for(self.intermediary)
        mixin = UserStampMixin()
        mixin.request = SimpleNamespace(user=user)
        component_type = equipment_models.ComponentType(name="Nuevo tipo")
        mixin._assign_organization(component_type)
        self.assertEqual(component_type.organization_id, self.intermediary.id)
