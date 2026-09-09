"""Tests for the ``apps.authentication.forms`` module."""

from unittest import mock

from allauth.account.forms import BaseSignupForm
from django import forms
from django.test import RequestFactory, TestCase

from apps.authentication import forms as auth_forms
from apps.users import models as users_models
from apps.users.factories import UserFactory


class CustomSignupFormTests(TestCase):
    """Tests for the :class:`CustomSignupForm`."""

    def setUp(self) -> None:
        self.request = RequestFactory().post("/authentication/signup/")

    def test_profile_fields_present(self) -> None:
        """The form exposes profile and credentials fields."""
        form = auth_forms.CustomSignupForm()
        for field in ("email", "password1", "password2", "first_name", "last_name"):
            self.assertIn(field, form.fields)

    def test_save_applies_profile_names(self) -> None:
        """``save`` copies the profile names onto the created user."""
        email = "signup@example.com"
        data = {
            "email": email,
            "password1": "Passw0rd!123",
            "password2": "Passw0rd!123",
            "first_name": "Ann",
            "last_name": "Lee",
        }
        form = auth_forms.CustomSignupForm(data=data)
        self.assertTrue(form.is_valid())

        def fake_signup_save(request) -> users_models.User:
            return users_models.User.objects.create_user(
                email=email, password="Passw0rd!123"
            )

        with mock.patch.object(BaseSignupForm, "save", side_effect=fake_signup_save):
            user = form.save(self.request)

        user.refresh_from_db()
        self.assertEqual(user.email, email)
        self.assertEqual(user.first_name, "Ann")
        self.assertEqual(user.last_name, "Lee")


class DeactivateAccountFormTests(TestCase):
    """Tests for the :class:`DeactivateAccountForm`."""

    def test_save_unknown_email_raises(self) -> None:
        """An unregistered email raises a validation error on save."""
        form = auth_forms.DeactivateAccountForm(data={"email": "ghost@example.com"})
        self.assertTrue(form.is_valid())
        with self.assertRaises(forms.ValidationError):
            form.save()

    def test_save_deactivates_existing_user(self) -> None:
        """A registered email deactivates its user on save."""
        user = UserFactory(is_active=True)
        form = auth_forms.DeactivateAccountForm(data={"email": user.email})
        self.assertTrue(form.is_valid())
        result = form.save()
        self.assertEqual(result, user)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
