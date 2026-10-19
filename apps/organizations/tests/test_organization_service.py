"""Tests for :class:`apps.organizations.services.OrganizationService`."""

from django.core.exceptions import ValidationError

from apps.organizations import models as organization_models
from apps.organizations.factories import OrganizationFactory
from apps.organizations.services import (
    MissingRootOrganization,
    MultipleRootOrganizations,
    OrganizationService,
)
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.users.factories import UserFactory


class OrganizationServiceTests(OrganizationTenantTestCase):
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

    def test_resolve_root_returns_the_single_root(self) -> None:
        """The one root of the schema is returned."""
        root = OrganizationFactory(slug="raiz")
        OrganizationFactory(parent=root)

        self.assertEqual(OrganizationService.resolve_root(), root)

    def test_resolve_root_raises_when_missing(self) -> None:
        """A required root that does not exist is an error, not ``None``."""
        with self.assertRaises(MissingRootOrganization):
            OrganizationService.resolve_root()

    def test_resolve_root_is_optional_when_asked(self) -> None:
        """Provisioning resolves an optional root before creating one."""
        self.assertIsNone(OrganizationService.resolve_root(required=False))

    def test_resolve_root_fails_when_ambiguous(self) -> None:
        """Two roots are never silently collapsed into an arbitrary one."""
        OrganizationFactory(slug="raiz-1")
        OrganizationFactory(slug="raiz-2")

        with self.assertRaises(MultipleRootOrganizations):
            OrganizationService.resolve_root()

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
