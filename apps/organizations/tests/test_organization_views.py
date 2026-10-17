"""Tests for the organization management views."""

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.organizations import models as organization_models
from apps.organizations.factories import OrganizationFactory
from apps.users.factories import UserFactory


def grant(user, *codenames: str) -> None:
    """Grant the given ``organizations`` permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        codename__in=codenames, content_type__app_label="organizations"
    )
    user.user_permissions.add(*permissions)


class OrganizationViewTests(TestCase):
    """CRUD, scoping and permission tests for the organization views."""

    def setUp(self) -> None:
        self.lab = OrganizationFactory(name="LAB")
        self.child = OrganizationFactory(name="Client Child", parent=self.lab)
        self.foreign = OrganizationFactory(name="Foreign Org")
        self.user = UserFactory(organization=self.lab)
        self.client.force_login(self.user)

    def test_list_requires_permission(self) -> None:
        """Authenticated users without ``view_organization`` are forbidden."""
        response = self.client.get(reverse("apps.organizations:organization_list"))
        self.assertEqual(response.status_code, 403)

    def test_list_only_shows_subtree(self) -> None:
        """The list shows the subtree and hides foreign organizations."""
        grant(self.user, "view_organization")
        response = self.client.get(reverse("apps.organizations:organization_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.child.name)
        self.assertNotContains(response, self.foreign.name)

    def test_create_assigns_created_by_and_slug(self) -> None:
        """Creating an organization stamps the author and generates a slug."""
        grant(self.user, "view_organization", "add_organization")
        response = self.client.post(
            reverse("apps.organizations:organization_create"),
            {
                "name": "Nueva Sucursal",
                "kind": "final",
                "parent": self.lab.pk,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("apps.organizations:organization_list"))
        organization = organization_models.Organization.objects.get(
            name="Nueva Sucursal"
        )
        self.assertEqual(organization.slug, "nueva-sucursal")
        self.assertEqual(organization.created_by, self.user)

    def test_create_form_renders(self) -> None:
        """The create form page renders for authorized users."""
        grant(self.user, "view_organization", "add_organization")
        response = self.client.get(reverse("apps.organizations:organization_create"))
        self.assertEqual(response.status_code, 200)

    def test_update_form_renders(self) -> None:
        """The update form page renders with the organization preloaded."""
        grant(self.user, "view_organization", "change_organization")
        response = self.client.get(
            reverse("apps.organizations:organization_update", args=[self.child.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.child.name)

    def test_update_rejects_out_of_scope_pk(self) -> None:
        """Editing an organization outside the subtree returns 404."""
        grant(self.user, "view_organization", "change_organization")
        response = self.client.post(
            reverse("apps.organizations:organization_update", args=[self.foreign.pk]),
            {"name": "Hacked", "kind": "final", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.name, "Foreign Org")

    def test_delete_blocked_with_children(self) -> None:
        """Review Focus #1: deleting a parent with children is refused."""
        grant(self.user, "delete_organization")
        response = self.client.post(
            reverse("apps.organizations:organization_delete", args=[self.lab.pk])
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            organization_models.Organization.objects.filter(pk=self.lab.pk).exists()
        )

    def test_delete_blocked_with_users(self) -> None:
        """Review Focus #1: deleting an org that still has users is refused."""
        grant(self.user, "delete_organization")
        org = OrganizationFactory(name="Client With User", parent=self.lab)
        UserFactory(organization=org)
        response = self.client.post(
            reverse("apps.organizations:organization_delete", args=[org.pk])
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            organization_models.Organization.objects.filter(pk=org.pk).exists()
        )

    def test_delete_leaf_succeeds(self) -> None:
        """A leaf organization with no users can be deleted."""
        grant(self.user, "delete_organization")
        response = self.client.post(
            reverse("apps.organizations:organization_delete", args=[self.child.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            organization_models.Organization.objects.filter(pk=self.child.pk).exists()
        )

    def test_delete_hides_foreign_organization(self) -> None:
        """Deleting an out-of-scope organization returns 404."""
        grant(self.user, "delete_organization")
        response = self.client.post(
            reverse("apps.organizations:organization_delete", args=[self.foreign.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            organization_models.Organization.objects.filter(pk=self.foreign.pk).exists()
        )
