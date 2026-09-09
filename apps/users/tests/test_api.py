"""Tests for the ``apps.users.api`` module."""

from allauth.account.models import EmailAddress
from django.test import TestCase
from django.urls import reverse

from apps.users.factories import UserFactory


class ToggleUserStatusViewTests(TestCase):
    """Tests for the toggle-user-status endpoint."""

    def setUp(self) -> None:
        self.operator = UserFactory(is_staff=True)
        self.target = UserFactory(is_active=False)
        self.client.force_login(self.operator)
        self.url = reverse("apps.users:toggle_user_status_api")

    def test_activate_user(self) -> None:
        """Posting ``activate`` reactivates the given user."""
        response = self.client.post(
            self.url, {"user_id": self.target.pk, "action": "activate"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["is_active"])
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_deactivate_user(self) -> None:
        """Posting ``deactivate`` disables the given user."""
        response = self.client.post(
            self.url, {"user_id": self.target.pk, "action": "deactivate"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["is_active"])
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_invalid_action(self) -> None:
        """An unknown action returns a failed JSON response."""
        response = self.client.post(
            self.url, {"user_id": self.target.pk, "action": "ban"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])

    def test_unknown_user_returns_404(self) -> None:
        """A non-existing user id returns a JSON 404 response."""
        response = self.client.post(self.url, {"user_id": 999999, "action": "activate"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])

    def test_anonymous_user_redirected(self) -> None:
        """Anonymous requests are redirected to the login page."""
        self.client.logout()
        response = self.client.post(
            self.url, {"user_id": self.target.pk, "action": "activate"}
        )
        self.assertEqual(response.status_code, 302)


class VerifyEmailViewTests(TestCase):
    """Tests for the verify-email endpoint."""

    def setUp(self) -> None:
        self.operator = UserFactory(is_staff=True)
        self.target = UserFactory()
        EmailAddress.objects.create(
            user=self.target,
            email=self.target.email,
            primary=True,
            verified=False,
        )
        self.client.force_login(self.operator)
        self.url = reverse("apps.users:verify_email_api")

    def test_missing_user_id(self) -> None:
        """Posting without a user id returns a failed JSON response."""
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])

    def test_verify_email(self) -> None:
        """Posting a valid user id marks its email as verified."""
        response = self.client.post(self.url, {"user_id": self.target.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        email = EmailAddress.objects.get(user=self.target)
        self.assertTrue(email.verified)

    def test_verify_email_for_unlinked_user(self) -> None:
        """A user without an EmailAddress record returns a JSON 404 response."""
        orphan = UserFactory()
        response = self.client.post(self.url, {"user_id": orphan.pk})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])
