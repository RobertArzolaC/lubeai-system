"""Tests for the organization detail view."""

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.organizations.factories import OrganizationFactory
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.users.factories import RoleFactory, UserFactory


def grant(user, *codenames: str) -> None:
    """Grant the given ``organizations`` permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        codename__in=codenames, content_type__app_label="organizations"
    )
    user.user_permissions.add(*permissions)


class OrganizationDetailTests(OrganizationTenantTestCase):
    """Rendering and scoping tests for the organization detail page."""

    def setUp(self) -> None:
        super().setUp()
        self.lab = OrganizationFactory(name="LAB")
        self.child = OrganizationFactory(name="Client Child", parent=self.lab)
        self.member = UserFactory(organization=self.lab, email="member@example.com")
        self.role = RoleFactory(organization=self.lab, name="Analista")
        self.user = UserFactory(organization=self.lab)
        self.client.force_login(self.user)

    def test_requires_permission(self) -> None:
        """Authenticated users without ``view_organization`` are forbidden."""
        response = self.client.get(
            reverse("apps.organizations:organization_detail", args=[self.lab.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_tabs_render_children_users_roles(self) -> None:
        """The detail page renders children, users and roles."""
        grant(self.user, "view_organization")
        response = self.client.get(
            reverse("apps.organizations:organization_detail", args=[self.lab.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.child.name)
        self.assertContains(response, self.member.email)
        self.assertContains(response, self.role.name)

    def test_out_of_scope_org_404s(self) -> None:
        """An organization outside the subtree is not found."""
        grant(self.user, "view_organization")
        foreign = OrganizationFactory(name="Foreign")
        response = self.client.get(
            reverse("apps.organizations:organization_detail", args=[foreign.pk])
        )
        self.assertEqual(response.status_code, 404)
