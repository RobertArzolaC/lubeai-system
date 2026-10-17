"""Tests for :class:`apps.organizations.services.OrganizationService`."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.organizations import models as organization_models
from apps.organizations.factories import OrganizationFactory
from apps.organizations.services import OrganizationService
from apps.users.factories import UserFactory


class OrganizationServiceTests(TestCase):
    """Tests for the organization slug and subtree helpers."""

    def test_slug_is_slugified_and_unique(self) -> None:
        """A colliding slug is suffixed."""
        OrganizationFactory(slug="minera-andina")
        self.assertEqual(
            OrganizationService.ensure_unique_slug("Minera Andina"), "minera-andina-2"
        )

    def test_slug_excludes_own_pk(self) -> None:
        """The organization's own slug is ignored when renaming."""
        org = OrganizationFactory(name="Minera Andina", slug="minera-andina")
        self.assertEqual(
            OrganizationService.ensure_unique_slug(org.name, exclude_pk=org.pk),
            "minera-andina",
        )

    def test_slug_falls_back_when_name_has_no_slug_chars(self) -> None:
        """A name without slug characters still yields a slug."""
        self.assertEqual(OrganizationService.ensure_unique_slug("!!!"), "organization")

    def test_cycle_parent_rejected(self) -> None:
        """Review Focus #4: cannot parent an org to its own descendant."""
        root = OrganizationFactory()
        child = OrganizationFactory(parent=root)
        with self.assertRaises(ValidationError):
            OrganizationService.assert_valid_parent(root, child)
        with self.assertRaises(ValidationError):
            OrganizationService.assert_valid_parent(root, root)

    def test_valid_parent_accepted(self) -> None:
        """A sibling/or outside the subtree is a valid parent."""
        root = OrganizationFactory()
        child = OrganizationFactory(parent=root)
        leaf = OrganizationFactory(parent=child)
        OrganizationService.assert_valid_parent(leaf, root)

    def test_none_parent_accepted(self) -> None:
        """A root organization (no parent) is valid."""
        OrganizationService.assert_valid_parent(OrganizationFactory(), None)

    def test_delete_organization_refuses_children(self) -> None:
        """Deleting an org with children raises instead of cascading."""
        root = OrganizationFactory()
        OrganizationFactory(parent=root)
        with self.assertRaises(ValidationError):
            OrganizationService.delete_organization(root)
        self.assertTrue(
            organization_models.Organization.objects.filter(pk=root.pk).exists()
        )

    def test_delete_organization_refuses_users(self) -> None:
        """Deleting an org with users raises instead of orphaning them."""
        organization = OrganizationFactory()
        UserFactory(organization=organization)
        with self.assertRaises(ValidationError):
            OrganizationService.delete_organization(organization)

    def test_delete_organization_removes_leaf(self) -> None:
        """A leaf organization with no users is deleted."""
        organization = OrganizationFactory()
        OrganizationService.delete_organization(organization)
        self.assertFalse(
            organization_models.Organization.objects.filter(
                pk=organization.pk
            ).exists()
        )

    def test_deactivate_cascades_to_descendants(self) -> None:
        """Deactivating a node deactivates its whole subtree."""
        root = OrganizationFactory()
        child = OrganizationFactory(parent=root)
        OrganizationService.deactivate(root)
        child.refresh_from_db()
        root.refresh_from_db()
        self.assertFalse(child.is_active)
        self.assertFalse(root.is_active)
        self.assertTrue(
            organization_models.Organization.objects.filter(pk=child.pk).exists()
        )
