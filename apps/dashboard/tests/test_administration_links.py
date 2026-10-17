"""Tests for the client administration entries in the sidebar and dashboard."""

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.organizations.factories import OrganizationFactory
from apps.users.factories import RoleFactory, UserFactory


def grant(user, app_label: str, *codenames: str) -> None:
    """Grant the given permission codenames of ``app_label`` to ``user``."""
    permissions = Permission.objects.filter(
        codename__in=codenames, content_type__app_label=app_label
    )
    user.user_permissions.add(*permissions)


class AdministrationLinksTests(TestCase):
    """Sidebar visibility and dashboard counts for the new modules."""

    def setUp(self) -> None:
        self.lab = OrganizationFactory(name="LAB")
        self.child = OrganizationFactory(name="Child", parent=self.lab)
        self.user = UserFactory(organization=self.lab)
        self.client.force_login(self.user)

    def test_sidebar_hides_clients_without_permissions(self) -> None:
        """Without permissions the client links are not rendered."""
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            f'href="{reverse("apps.organizations:organization_list")}"',
        )
        self.assertNotContains(response, f'href="{reverse("apps.users:user_list")}"')

    def test_sidebar_shows_clients_with_permissions(self) -> None:
        """With permissions the client links are rendered."""
        grant(self.user, "organizations", "view_organization")
        grant(self.user, "users", "view_user", "view_role")
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(
            response,
            f'href="{reverse("apps.organizations:organization_list")}"',
        )
        self.assertContains(response, f'href="{reverse("apps.users:user_list")}"')
        self.assertContains(response, f'href="{reverse("apps.users:role_list")}"')

    def test_dashboard_counts_scoped(self) -> None:
        """Counts only include organizations and users within the subtree."""
        UserFactory(organization=self.child)
        UserFactory(organization=OrganizationFactory())
        RoleFactory(organization=self.lab)
        RoleFactory(organization=OrganizationFactory())
        grant(self.user, "organizations", "view_organization")
        grant(self.user, "users", "view_user", "view_role")

        response = self.client.get(reverse("apps.dashboard:index"))

        counts = response.context["client_counts"]
        self.assertEqual(counts["organizations"], 2)
        self.assertEqual(counts["users"], 2)
        self.assertEqual(counts["roles"], 1)

    def test_dashboard_flag_false_without_permissions(self) -> None:
        """The administration block stays hidden without permissions."""
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertFalse(response.context["show_client_administration"])
