"""Tests for the ``apps.users.managers`` module."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users import models as users_models

User = get_user_model()


class CustomUserManagerTests(TestCase):
    """Tests for the :class:`CustomUserManager`."""

    def test_create_user_success(self) -> None:
        """``create_user`` persists a user identified by email."""
        user = users_models.User.objects.create_user(
            email="alice@example.com", password="Passw0rd!123"
        )
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(user.check_password("Passw0rd!123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_normalizes_email(self) -> None:
        """Emails are normalized (trimmed and lowercased)."""
        user = users_models.User.objects.create_user(
            email="  Alice@Example.COM ", password="Passw0rd!123"
        )
        self.assertEqual(user.email, "Alice@example.com")

    def test_create_user_without_email_raises_value_error(self) -> None:
        """Creating a user without email raises ``ValueError``."""
        with self.assertRaises(ValueError):
            users_models.User.objects.create_user(email="", password="Passw0rd!123")

    def test_create_superuser_sets_flags(self) -> None:
        """``create_superuser`` grants staff and superuser flags."""
        user = users_models.User.objects.create_superuser(
            email="root@example.com", password="Passw0rd!123"
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_create_superuser_requires_staff_flag(self) -> None:
        """``create_superuser`` rejects users without ``is_staff``."""
        with self.assertRaises(ValueError):
            users_models.User.objects.create_superuser(
                email="root@example.com",
                password="Passw0rd!123",
                is_staff=False,
            )

    def test_create_superuser_requires_superuser_flag(self) -> None:
        """``create_superuser`` rejects users without ``is_superuser``."""
        with self.assertRaises(ValueError):
            users_models.User.objects.create_superuser(
                email="root@example.com",
                password="Passw0rd!123",
                is_superuser=False,
            )
