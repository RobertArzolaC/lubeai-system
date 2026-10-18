"""Tests for the user management views."""

from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.organizations.factories import OrganizationFactory
from apps.users import models as users_models
from apps.users.factories import RoleFactory, UserFactory
from apps.users.tests.base import UserTenantTestCase


def grant(user, *codenames: str) -> None:
    """Grant the given ``users`` permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        codename__in=codenames, content_type__app_label="users"
    )
    user.user_permissions.add(*permissions)


class UserViewTests(UserTenantTestCase):
    """CRUD, scoping and permission tests for the user views."""

    def setUp(self) -> None:
        super().setUp()
        self.lab = OrganizationFactory()
        self.child = OrganizationFactory(parent=self.lab)
        self.member = UserFactory(organization=self.child, email="member@example.com")
        self.foreign = UserFactory(
            organization=OrganizationFactory(), email="foreign@example.com"
        )
        self.actor = UserFactory(organization=self.lab)
        self.client.force_login(self.actor)

    def test_list_requires_permission(self) -> None:
        """Authenticated users without ``view_user`` are forbidden."""
        response = self.client.get(reverse("apps.users:user_list"))
        self.assertEqual(response.status_code, 403)

    def test_list_scoped_to_subtree(self) -> None:
        """The list shows subtree users and hides foreign ones."""
        grant(self.actor, "view_user")
        response = self.client.get(reverse("apps.users:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.email)
        self.assertNotContains(response, self.foreign.email)

    def test_create_delegates_to_service(self) -> None:
        """Posting the form creates the user through the service."""
        grant(self.actor, "view_user", "add_user")
        role = RoleFactory(organization=self.child)
        response = self.client.post(
            reverse("apps.users:user_create"),
            {
                "organization": self.child.pk,
                "first_name": "Nuevo",
                "last_name": "Usuario",
                "email": "nuevo@example.com",
                "is_active": "on",
                "roles": [role.pk],
            },
        )
        self.assertRedirects(response, reverse("apps.users:user_list"))
        user = users_models.User.objects.get(email="nuevo@example.com")
        self.assertEqual(user.organization, self.child)
        self.assertIn(role.group, user.groups.all())

    def test_create_form_renders(self) -> None:
        """The create form renders for authorized users."""
        grant(self.actor, "view_user", "add_user")
        response = self.client.get(reverse("apps.users:user_create"))
        self.assertEqual(response.status_code, 200)

    def test_update_changes_user(self) -> None:
        """Updating a user changes its names and status."""
        grant(self.actor, "view_user", "change_user")
        response = self.client.post(
            reverse("apps.users:user_update", args=[self.member.pk]),
            {
                "organization": self.child.pk,
                "first_name": "Cambiado",
                "last_name": "Apellido",
                "email": self.member.email,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("apps.users:user_list"))
        self.member.refresh_from_db()
        self.assertEqual(self.member.first_name, "Cambiado")

    def test_update_rejects_out_of_scope_pk(self) -> None:
        """Editing a foreign user returns 404."""
        grant(self.actor, "view_user", "change_user")
        response = self.client.post(
            reverse("apps.users:user_update", args=[self.foreign.pk]),
            {
                "organization": self.foreign.organization_id,
                "first_name": "Hack",
                "last_name": "User",
                "email": self.foreign.email,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_deactivates_not_destroys(self) -> None:
        """Deleting a user only deactivates it."""
        grant(self.actor, "view_user", "delete_user")
        response = self.client.post(
            reverse("apps.users:user_delete", args=[self.member.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertTrue(users_models.User.objects.filter(pk=self.member.pk).exists())
