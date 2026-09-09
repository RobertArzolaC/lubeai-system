"""Tests for the ``add_default_users`` management command."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.users import models as users_models

User = get_user_model()


class AddDefaultUsersCommandTests(TestCase):
    """Tests for the ``add_default_users`` management command."""

    def test_command_creates_default_users(self) -> None:
        """Running the command creates the superuser and the staff users."""
        call_command("add_default_users", stdout=StringIO())
        admin = User.objects.get(email="admin@example.com")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(User.objects.filter(email="staff1@example.com").exists())
        self.assertTrue(User.objects.filter(email="staff2@example.com").exists())
        self.assertEqual(
            users_models.Account.objects.filter(
                user__email__in=[
                    "admin@example.com",
                    "staff1@example.com",
                    "staff2@example.com",
                ]
            ).count(),
            3,
        )

    def test_command_is_idempotent(self) -> None:
        """Running the command twice does not duplicate users."""
        call_command("add_default_users", stdout=StringIO())
        output = StringIO()
        call_command("add_default_users", stdout=output)
        self.assertEqual(User.objects.count(), 3)
        self.assertIn("already exists", output.getvalue())
