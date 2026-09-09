"""Tests for the ``apps.authentication.views`` module."""

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.users.factories import UserFactory

OLD_PASSWORD = "Passw0rd!123"
NEW_PASSWORD = "NewPassw0rd!456"


class ChangePasswordViewTests(TestCase):
    """Tests for the change-password endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(password=OLD_PASSWORD)
        self.client.force_login(self.user)
        self.url = reverse("apps.authentication:api_change_password")

    def test_wrong_old_password_returns_400(self) -> None:
        """An incorrect old password returns an error JSON response."""
        response = self.client.post(
            self.url,
            {
                "old_password": "wrong-old",
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    def test_change_password_success(self) -> None:
        """Valid credentials update the user password."""
        response = self.client.post(
            self.url,
            {
                "old_password": OLD_PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))


class DeactivateAccountViewTests(TestCase):
    """Tests for the deactivate-account endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(is_active=True)
        self.client.force_login(self.user)
        self.url = reverse("apps.authentication:api_deactivate_account")

    def test_unknown_email_returns_400(self) -> None:
        """An unregistered email returns an error JSON response."""
        response = self.client.post(self.url, {"email": "ghost@example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    def test_deactivate_success(self) -> None:
        """A registered email deactivates the related user."""
        response = self.client.post(self.url, {"email": self.user.email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


STRONG_PASSWORD = "9fK2!vX7qL4zM"


class ValidatePasswordViewTests(TestCase):
    """Tests for the live password-validation endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory()
        self.url = reverse("apps.authentication:validate_password_api")

    def test_anonymous_user_redirected(self) -> None:
        """Anonymous requests are redirected to login."""
        response = self.client.post(self.url, {"password": STRONG_PASSWORD})
        self.assertEqual(response.status_code, 302)

    def test_strong_password_returns_all_passed(self) -> None:
        """A strong password yields checks all marked as passed."""
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"password": STRONG_PASSWORD})
        self.assertEqual(response.status_code, 200)
        checks = response.json()["checks"]
        self.assertTrue(checks)
        for check in checks:
            self.assertTrue(check["passed"], msg=check["id"])

    def test_weak_password_returns_some_unpassed(self) -> None:
        """A purely numeric password reports failures."""
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"password": "12345678"})
        self.assertEqual(response.status_code, 200)
        checks = response.json()["checks"]
        self.assertTrue(any(not c["passed"] for c in checks))

    def test_empty_password_returns_all_unpassed(self) -> None:
        """Missing input is reported as not yet valid, not as an error."""
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"password": ""})
        self.assertEqual(response.status_code, 200)
        checks = response.json()["checks"]
        self.assertTrue(checks)
        for check in checks:
            self.assertFalse(check["passed"])


PASSWORD_CHANGE_URL = "/authentication/password/change/"
CHANGE_NEW_PASSWORD = "9fK2!vX7qL4zM"
CHANGE_NEW_PASSWORD_MISMATCH = "9fK2!vX7qL4zN"


@override_settings(ACCOUNT_RATE_LIMITS={"change_password": "1000/m/user"})
class PasswordChangeViewTests(TestCase):
    """Tests for the project password-change page."""

    def setUp(self) -> None:
        self.user = UserFactory(password="Passw0rd!123")
        self.client.force_login(self.user)

    def test_url_name_resolves(self) -> None:
        """The allauth URL name points to the overridden project route."""
        self.assertEqual(reverse("account_change_password"), PASSWORD_CHANGE_URL)

    def test_anonymous_user_redirected_to_login(self) -> None:
        """Anonymous users cannot reach the password change page."""
        self.client.logout()
        response = self.client.get(PASSWORD_CHANGE_URL)
        self.assertEqual(response.status_code, 302)

    def test_page_renders_with_template_and_checks(self) -> None:
        """Authenticated users see the dashboard template with the checklist."""
        response = self.client.get(PASSWORD_CHANGE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/password_change.html")
        checks = response.context["password_checks"]
        self.assertTrue(checks)
        for check in checks:
            self.assertFalse(check["passed"])

    def test_valid_change_redirects_to_settings_and_updates_password(self) -> None:
        """A valid submission updates the password and keeps the session."""
        response = self.client.post(
            PASSWORD_CHANGE_URL,
            {
                "oldpassword": "Passw0rd!123",
                "password1": CHANGE_NEW_PASSWORD,
                "password2": CHANGE_NEW_PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("apps.users:settings"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CHANGE_NEW_PASSWORD))
        # Session must survive the password hash rotation.
        settings_response = self.client.get(reverse("apps.users:settings"))
        self.assertEqual(settings_response.status_code, 200)

    def test_wrong_old_password_rerenders_with_error(self) -> None:
        """An incorrect current password keeps the user on the page."""
        response = self.client.post(
            PASSWORD_CHANGE_URL,
            {
                "oldpassword": "WrongPassw0rd!",
                "password1": CHANGE_NEW_PASSWORD,
                "password2": CHANGE_NEW_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("oldpassword", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Passw0rd!123"))

    def test_mismatched_new_passwords_rerenders_with_error(self) -> None:
        """Non-matching confirmation passwords do not change the password."""
        response = self.client.post(
            PASSWORD_CHANGE_URL,
            {
                "oldpassword": "Passw0rd!123",
                "password1": CHANGE_NEW_PASSWORD,
                "password2": CHANGE_NEW_PASSWORD_MISMATCH,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("password2", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Passw0rd!123"))
