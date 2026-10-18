"""Tests for the ``apps.users.forms`` module."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users import forms as users_forms
from apps.users.factories import UserFactory
from apps.users.tests.base import UserTenantTestCase

User = get_user_model()


class CustomUserCreationFormTests(TestCase):
    """Tests for :class:`CustomUserCreationForm`."""

    def test_meta_model_is_user(self) -> None:
        """The form targets the custom User model with the email field."""
        self.assertEqual(users_forms.CustomUserCreationForm.Meta.model, User)
        self.assertEqual(users_forms.CustomUserCreationForm.Meta.fields, ("email",))

    def test_creation_fields_present(self) -> None:
        """Email and password fields are exposed by the form."""
        form = users_forms.CustomUserCreationForm()
        self.assertIn("email", form.fields)
        self.assertIn("password1", form.fields)
        self.assertIn("password2", form.fields)


class CustomUserChangeFormTests(TestCase):
    """Tests for :class:`CustomUserChangeForm`."""

    def test_meta_model_is_user(self) -> None:
        """The form targets the custom User model with the email field."""
        self.assertEqual(users_forms.CustomUserChangeForm.Meta.model, User)
        self.assertEqual(users_forms.CustomUserChangeForm.Meta.fields, ("email",))


class UserSettingsFormTests(UserTenantTestCase):
    """Tests for :class:`UserSettingsForm`."""

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory(first_name="Old", last_name="Name")

    def test_valid_data_updates_user(self) -> None:
        """Valid data updates the user first and last names."""
        form = users_forms.UserSettingsForm(
            data={"first_name": "New", "last_name": "Person"},
            instance=self.user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Person")

    def test_last_name_is_optional(self) -> None:
        """A missing last name is accepted by the form."""
        form = users_forms.UserSettingsForm(
            data={"first_name": "Only"}, instance=self.user
        )
        self.assertTrue(form.is_valid())
