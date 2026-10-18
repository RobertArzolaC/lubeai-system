"""Tests for the ``apps.users.views`` module."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.users.factories import UserFactory

AVATAR_MEDIA_ROOT = "/tmp/django_template_avatar_tests"


class ProfileViewTests(TestCase):
    """Tests for :class:`ProfileView`."""

    def setUp(self) -> None:
        self.user = UserFactory()
        self.url = reverse("apps.users:profile")

    def test_anonymous_user_redirected_to_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_profile_page_renders(self) -> None:
        """Authenticated users can access their profile page."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")


@override_settings(MEDIA_ROOT=AVATAR_MEDIA_ROOT)
class SettingsViewTests(TestCase):
    """Tests for :class:`SettingsView`."""

    def setUp(self) -> None:
        self.user = UserFactory(first_name="Old", last_name="Name")
        self.client.force_login(self.user)
        self.url = reverse("apps.users:settings")

    def avatar_file(self) -> SimpleUploadedFile:
        """Return a tiny image payload for avatar uploads."""
        return SimpleUploadedFile(
            "avatar.png", b"file-content", content_type="image/png"
        )

    def test_settings_page_renders(self) -> None:
        """Authenticated users can access their settings page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/settings.html")

    def test_settings_context_has_no_account_form(self) -> None:
        """Settings no longer exposes an Account form."""
        response = self.client.get(self.url)
        self.assertNotIn("account_form", response.context)

    def test_post_updates_user_profile(self) -> None:
        """Posting valid data updates the user profile and redirects."""
        response = self.client.post(
            self.url, {"first_name": "New", "last_name": "Person"}
        )
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Person")

    def test_post_updates_avatar(self) -> None:
        """Posting an avatar file stores it on the user."""
        response = self.client.post(
            self.url,
            {"first_name": "Old", "last_name": "Name", "avatar": self.avatar_file()},
        )
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)

    def test_post_without_avatar_keeps_existing_avatar(self) -> None:
        """Saving only profile data does not wipe the current avatar."""
        self.user.avatar = "users/avatars/existing.png"
        self.user.save(update_fields=["avatar"])
        response = self.client.post(
            self.url, {"first_name": "New", "last_name": "Name"}
        )
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar.name, "users/avatars/existing.png")

    def test_post_removes_avatar(self) -> None:
        """Posting ``avatar_remove`` clears the current avatar."""
        self.user.avatar = "users/avatars/existing.png"
        self.user.save(update_fields=["avatar"])
        response = self.client.post(
            self.url,
            {"first_name": "Old", "last_name": "Name", "avatar_remove": "1"},
        )
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)


class AccountsUIRemovedTests(TestCase):
    """The legacy Accounts UI is gone in favour of the Users UI."""

    def test_account_urls_are_removed(self) -> None:
        """No ``account_*`` URL name is routable anymore."""
        with self.assertRaises(NoReverseMatch):
            reverse("apps.users:account_list")
