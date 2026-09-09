"""Tests for the ``apps.authentication.services`` module."""

from django.test import TestCase

from apps.authentication import services
from apps.users.factories import UserFactory

STRONG_PASSWORD = "9fK2!vX7qL4zM"


class GetPasswordChecksTests(TestCase):
    """Tests for :func:`get_password_checks`."""

    def setUp(self) -> None:
        self.user = UserFactory()

    def test_empty_password_returns_all_unpassed(self) -> None:
        """With no password every check reports ``passed=False``."""
        checks = services.get_password_checks(None, user=self.user)
        self.assertTrue(checks)
        for check in checks:
            self.assertIn("id", check)
            self.assertIn("label", check)
            self.assertFalse(check["passed"])

    def test_numeric_password_fails_numeric_check_only(self) -> None:
        """A purely numeric password fails the numeric validator but not length."""
        checks = services.get_password_checks("12345678", user=self.user)
        by_id = {c["id"]: c for c in checks}
        self.assertFalse(by_id["NumericPasswordValidator"]["passed"])
        self.assertTrue(by_id["MinimumLengthValidator"]["passed"])

    def test_strong_password_passes_all_checks(self) -> None:
        """A strong random password passes every configured validator."""
        checks = services.get_password_checks(STRONG_PASSWORD, user=self.user)
        self.assertTrue(checks)
        for check in checks:
            self.assertTrue(check["passed"], msg=check["id"])
