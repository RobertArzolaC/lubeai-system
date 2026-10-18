"""Tests for the ``add_default_users`` management command family."""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django_tenants.management.commands import BaseTenantCommand

from apps.users.management.commands import add_default_users
from apps.users.tests.base import UserTenantTestCase

User = get_user_model()


class AddDefaultUsersTenantCommandTests(TestCase):
    """The public command iterates every tenant schema."""

    def test_command_is_a_tenant_command(self) -> None:
        """Running it once per schema is what makes it multi-tenant safe."""
        self.assertTrue(issubclass(add_default_users.Command, BaseTenantCommand))


class AddDefaultUsersCommandTests(UserTenantTestCase):
    """Tests for the ``add_default_users`` management command."""

    def run_command(self, output: StringIO) -> None:
        """Run the command against this test's tenant schema."""
        call_command(
            "add_default_users",
            schema=self.tenant.schema_name,
            stdout=output,
        )

    def test_command_creates_default_users(self) -> None:
        """Running the command creates the superuser and the staff users."""
        self.run_command(StringIO())

        admin = User.objects.get(email="admin@example.com")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(User.objects.filter(email="staff1@example.com").exists())
        self.assertTrue(User.objects.filter(email="staff2@example.com").exists())
        self.assertEqual(User.objects.count(), 3)

    def test_command_is_idempotent(self) -> None:
        """Running the command twice does not duplicate users."""
        self.run_command(StringIO())
        output = StringIO()
        self.run_command(output)

        self.assertEqual(User.objects.count(), 3)
        self.assertIn("already exists", output.getvalue())
