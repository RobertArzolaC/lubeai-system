"""Tests for :class:`apps.users.services.UserService`."""

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.organizations.factories import OrganizationFactory
from apps.users import models as users_models
from apps.users.factories import RoleFactory, UserFactory
from apps.users.services import UserService


class UserServiceTests(TestCase):
    """Tests for creating and updating users with roles."""

    def setUp(self) -> None:
        self.organization = OrganizationFactory()
        self.actor = UserFactory(organization=self.organization)

    def test_create_builds_user_account_and_email(self) -> None:
        """Creating a user also provisions an account and a pending email."""
        user = UserService().create_user(
            actor=self.actor,
            email="nuevo@example.com",
            first_name="Nuevo",
            last_name="Usuario",
            organization=self.organization,
        )
        self.assertTrue(users_models.Account.objects.filter(user=user).exists())
        self.assertTrue(EmailAddress.objects.filter(user=user, verified=False).exists())

    def test_create_assigns_organization_and_roles(self) -> None:
        """The created user belongs to the organization and carries its roles."""
        role = RoleFactory(organization=self.organization)
        user = UserService().create_user(
            actor=self.actor,
            email="nuevo@example.com",
            first_name="Nuevo",
            last_name="Usuario",
            organization=self.organization,
            roles=[role],
        )
        self.assertEqual(user.organization, self.organization)
        self.assertIn(role.group, user.groups.all())

    def test_duplicate_email_raises(self) -> None:
        """Review Focus #5: a duplicate email fails with a validation error."""
        UserFactory(email="dup@example.com")
        with self.assertRaises(ValidationError):
            UserService().create_user(
                actor=self.actor,
                email="dup@example.com",
                first_name="Dup",
                last_name="User",
                organization=self.organization,
            )

    def test_set_roles_preserves_unrelated_groups(self) -> None:
        """Only groups backing a role are replaced."""
        user = UserFactory()
        other = Group.objects.create(name="legacy")
        user.groups.add(other)
        role = RoleFactory(organization=self.organization)

        UserService().set_roles(user, [role])

        self.assertIn(other, user.groups.all())
        self.assertIn(role.group, user.groups.all())

    def test_set_roles_replaces_previous_role_groups(self) -> None:
        """A second assignment removes the previously assigned roles."""
        user = UserFactory()
        first = RoleFactory(organization=self.organization)
        second = RoleFactory(organization=self.organization)
        UserService().set_roles(user, [first])
        UserService().set_roles(user, [second])
        self.assertNotIn(first.group, user.groups.all())
        self.assertIn(second.group, user.groups.all())

    def test_update_changes_fields_and_roles(self) -> None:
        """Updating a user changes its data and role assignment."""
        user = UserFactory(organization=self.organization)
        role = RoleFactory(organization=self.organization)
        updated = UserService().update_user(
            user,
            first_name="Ana",
            last_name="Perez",
            organization=self.organization,
            roles=[role],
            is_active=False,
        )
        updated.refresh_from_db()
        self.assertEqual(updated.first_name, "Ana")
        self.assertEqual(updated.last_name, "Perez")
        self.assertFalse(updated.is_active)
        self.assertIn(role.group, updated.groups.all())
