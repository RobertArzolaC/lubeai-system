"""Tests for the role management views."""

from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from apps.organizations import factories as organization_factories
from apps.users import models as users_models
from apps.users.factories import RoleFactory, UserFactory
from apps.users.tests.base import UserTenantTestCase


def grant(user, *codenames: str) -> None:
    """Grant the given ``users`` permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        codename__in=codenames, content_type__app_label="users"
    )
    user.user_permissions.add(*permissions)


class RoleViewTests(UserTenantTestCase):
    """CRUD and permission tests for the role views."""

    def setUp(self) -> None:
        super().setUp()
        self.lab = organization_factories.OrganizationFactory()
        organization_factories.OrganizationFactory(parent=self.lab)
        self.user = UserFactory(organization=self.lab)
        self.client.force_login(self.user)

    def test_list_requires_permission(self) -> None:
        """Authenticated users without ``view_role`` are forbidden."""
        response = self.client.get(reverse("apps.users:role_list"))
        self.assertEqual(response.status_code, 403)

    def test_list_renders_with_permission(self) -> None:
        """Granted users see the role list."""
        grant(self.user, "view_role")
        RoleFactory(organization=self.lab, name="Analista")
        response = self.client.get(reverse("apps.users:role_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analista")

    def test_create_persists_role_and_permissions(self) -> None:
        """Posting the form creates the role with the selected permissions."""
        grant(self.user, "view_role", "add_role")
        permissions = list(Permission.objects.filter(codename="view_report")[:1])
        response = self.client.post(
            reverse("apps.users:role_create"),
            {
                "organization": self.lab.pk,
                "name": "Analista",
                "description": "Reads reports",
                "is_active": "on",
                "permissions": [permission.pk for permission in permissions],
            },
        )
        self.assertRedirects(response, reverse("apps.users:role_list"))
        role = users_models.Role.objects.get(name="Analista")
        self.assertEqual(role.group.permissions.count(), len(permissions))

    def test_create_rejects_foreign_organization(self) -> None:
        """Review Focus #3: an org outside the subtree is rejected."""
        grant(self.user, "add_role")
        foreign = organization_factories.OrganizationFactory()
        response = self.client.post(
            reverse("apps.users:role_create"),
            {
                "organization": foreign.pk,
                "name": "Analista",
                "description": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(users_models.Role.objects.exists())

    def test_update_changes_permissions(self) -> None:
        """Updating a role replaces its permission set."""
        grant(self.user, "view_role", "change_role")
        role = RoleFactory(organization=self.lab)
        permission = Permission.objects.get(codename="view_report")
        response = self.client.post(
            reverse("apps.users:role_update", args=[role.pk]),
            {
                "organization": self.lab.pk,
                "name": role.name,
                "description": role.description,
                "is_active": "on",
                "permissions": [permission.pk],
            },
        )
        self.assertRedirects(response, reverse("apps.users:role_list"))
        role.refresh_from_db()
        self.assertEqual(list(role.group.permissions.all()), [permission])

    def test_update_cannot_move_role_across_organizations(self) -> None:
        """The owning organization is immutable on update."""
        grant(self.user, "view_role", "change_role")
        role = RoleFactory(organization=self.lab)
        foreign = organization_factories.OrganizationFactory()
        response = self.client.post(
            reverse("apps.users:role_update", args=[role.pk]),
            {
                "organization": foreign.pk,
                "name": role.name,
                "description": role.description,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        role.refresh_from_db()
        self.assertEqual(role.organization, self.lab)

    def test_delete_removes_group(self) -> None:
        """Deleting a role through the view removes its backing group."""
        grant(self.user, "delete_role")
        role = RoleFactory(organization=self.lab)
        group_id = role.group_id
        response = self.client.post(reverse("apps.users:role_delete", args=[role.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Group.objects.filter(pk=group_id).exists())
