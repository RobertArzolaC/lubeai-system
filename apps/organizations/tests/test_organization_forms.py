"""Tests for :class:`apps.organizations.forms.OrganizationForm`."""

from apps.organizations import models as organization_models
from apps.organizations.factories import OrganizationFactory
from apps.organizations.forms import OrganizationForm
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.users.factories import UserFactory


class OrganizationFormTests(OrganizationTenantTestCase):
    """Validation and scoping tests for the organization form."""

    def test_generates_slug_from_name(self) -> None:
        """A blank slug is derived from the name on save."""
        user = UserFactory()
        form = OrganizationForm({"name": "Nueva Planta", "kind": "final"}, user=user)
        self.assertTrue(form.is_valid(), form.errors)
        organization = form.save()
        self.assertEqual(organization.slug, "nueva-planta")

    def test_generates_unique_slug_on_collision(self) -> None:
        """A colliding slug is suffixed on save."""
        OrganizationFactory(slug="nueva-planta")
        form = OrganizationForm({"name": "Nueva Planta", "kind": "final"})
        self.assertTrue(form.is_valid(), form.errors)
        organization = form.save()
        self.assertEqual(organization.slug, "nueva-planta-2")

    def test_parent_queryset_scoped_to_user_subtree(self) -> None:
        """Only organizations in the user's subtree are offered as parents."""
        lab = OrganizationFactory()
        child = OrganizationFactory(parent=lab)
        foreign = OrganizationFactory()
        user = UserFactory(organization=lab)

        form = OrganizationForm(user=user)

        self.assertIn(child, form.fields["parent"].queryset)
        self.assertNotIn(foreign, form.fields["parent"].queryset)

    def test_rejects_foreign_parent(self) -> None:
        """Review Focus #3: a parent outside the subtree is rejected."""
        lab = OrganizationFactory()
        OrganizationFactory(parent=lab)
        foreign = OrganizationFactory()
        user = UserFactory(organization=lab)

        form = OrganizationForm(
            {"name": "X", "kind": "final", "parent": foreign.pk}, user=user
        )

        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)

    def test_rejects_cycle_parent(self) -> None:
        """Review Focus #4: an organization cannot parent to its descendant."""
        root = OrganizationFactory()
        child = OrganizationFactory(parent=root)
        OrganizationFactory(parent=root)
        user = UserFactory(organization=root)

        form = OrganizationForm(
            {"name": root.name, "kind": root.kind, "parent": child.pk},
            instance=root,
            user=user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)

    def test_non_superuser_cannot_pick_platform_kind(self) -> None:
        """Only superusers may create a platform organization."""
        form = OrganizationForm({"name": "X", "kind": "platform"}, user=UserFactory())
        self.assertFalse(form.is_valid())
        self.assertIn("kind", form.errors)

    def test_superuser_can_pick_platform_kind(self) -> None:
        """A superuser may create a platform organization."""
        user = UserFactory(is_superuser=True)
        form = OrganizationForm({"name": "Platform X", "kind": "platform"}, user=user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().kind, "platform")

    def test_updating_does_not_change_slug(self) -> None:
        """Editing an organization keeps its existing slug."""
        organization = OrganizationFactory(name="Old", slug="old")
        form = OrganizationForm(
            {"name": "New", "kind": organization.kind}, instance=organization
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        organization.refresh_from_db()
        self.assertEqual(
            organization_models.Organization.objects.get(pk=organization.pk).slug,
            "old",
        )
