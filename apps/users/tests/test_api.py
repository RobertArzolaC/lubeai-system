"""Tests for the ``apps.users.api`` module."""

from django.urls import reverse

from apps.users.factories import UserFactory
from apps.users.tests.base import UserTenantTestCase


class ToggleUserStatusViewTests(UserTenantTestCase):
    """Tests for the toggle-user-status endpoint."""

    def setUp(self) -> None:
        super().setUp()
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
