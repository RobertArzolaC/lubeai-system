"""Tests for the ``apps.users.forms`` module."""

from unittest import mock

from allauth.account.forms import BaseSignupForm
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.users import forms as users_forms
from apps.users import models as users_models
from apps.users.factories import UserFactory

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


class UserSettingsFormTests(TestCase):
    """Tests for :class:`UserSettingsForm`."""

    def setUp(self) -> None:
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


class AccountSettingsFormTests(TestCase):
    """Tests for :class:`AccountSettingsForm`."""

    def test_meta_targets_account(self) -> None:
        """The form targets the Account model with all fields."""
        self.assertEqual(
            users_forms.AccountSettingsForm.Meta.model, users_models.Account
        )
        self.assertEqual(users_forms.AccountSettingsForm.Meta.fields, "__all__")


class AccountCreationFormTests(TestCase):
    """Tests for :class:`AccountCreationForm`."""

    def setUp(self) -> None:
        self.request = RequestFactory().post("/users/accounts/create/")

    def test_password_fields_removed(self) -> None:
        """Password fields are not exposed on the account creation form."""
        form = users_forms.AccountCreationForm()
        self.assertNotIn("password1", form.fields)
        self.assertNotIn("password2", form.fields)

    def test_permission_fields_present(self) -> None:
        """Permission checkbox fields are exposed by the form."""
        form = users_forms.AccountCreationForm()
        self.assertIn("can_view_account", form.fields)
        self.assertIn("can_add_account", form.fields)

    def test_clean_raises_on_existing_email(self) -> None:
        """Using an email already registered makes the form invalid."""
        UserFactory(email="taken@example.com")
        form = users_forms.AccountCreationForm(
            data={
                "email": "taken@example.com",
                "first_name": "A",
                "last_name": "B",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_save_applies_names_password_and_permissions(self) -> None:
        """``save`` persists profile data, resets the password and grants permissions."""
        email = "brand.new@example.com"
        data = {
            "email": email,
            "first_name": "Brand",
            "last_name": "New",
            "can_view_account": "on",
        }
        form = users_forms.AccountCreationForm(data=data)
        self.assertTrue(form.is_valid())

        def fake_signup_save(request) -> User:
            return users_models.User.objects.create_user(
                email=email, password="Passw0rd!123"
            )

        with (
            mock.patch.object(BaseSignupForm, "save", side_effect=fake_signup_save),
            mock.patch("apps.users.forms.config") as cfg,
        ):
            cfg.ENABLE_SEND_EMAIL = False
            user = form.save(self.request)

        user.refresh_from_db()
        self.assertEqual(user.first_name, "Brand")
        self.assertEqual(user.last_name, "New")
        self.assertFalse(user.check_password("Passw0rd!123"))
        self.assertTrue(user.has_perm("users.view_account"))
        self.assertFalse(user.has_perm("users.add_account"))
        email_address = EmailAddress.objects.get(user=user, email=email)
        self.assertFalse(email_address.verified)

    def test_save_sends_confirmation_when_enabled(self) -> None:
        """When email sending is enabled the confirmation is dispatched."""
        email = "mailer@example.com"
        data = {
            "email": email,
            "first_name": "Mail",
            "last_name": "Er",
        }
        form = users_forms.AccountCreationForm(data=data)
        self.assertTrue(form.is_valid())

        def fake_signup_save(request) -> User:
            return users_models.User.objects.create_user(
                email=email, password="Passw0rd!123"
            )

        with (
            mock.patch.object(BaseSignupForm, "save", side_effect=fake_signup_save),
            mock.patch("apps.users.forms.config") as cfg,
            mock.patch.object(EmailAddress, "send_confirmation") as send_confirmation,
        ):
            cfg.ENABLE_SEND_EMAIL = True
            form.save(self.request)
            send_confirmation.assert_called_once_with(self.request, signup=True)


class AccountUpdateFormTests(TestCase):
    """Tests for :class:`AccountUpdateForm`."""

    def setUp(self) -> None:
        self.user = UserFactory(first_name="Jane", last_name="Doe")
        self.account = self.user.account

    def test_initial_values_from_user(self) -> None:
        """Initial values mirror the linked user profile."""
        form = users_forms.AccountUpdateForm(instance=self.account, user=self.user)
        self.assertEqual(form.fields["first_name"].initial, "Jane")
        self.assertEqual(form.fields["last_name"].initial, "Doe")
        self.assertEqual(form.fields["email"].initial, self.user.email)

    def test_save_updates_user_and_account(self) -> None:
        """``save`` persists profile changes on the linked user."""
        data = {"first_name": "Janet", "last_name": "Doe", "avatar": ""}
        form = users_forms.AccountUpdateForm(
            data=data, instance=self.account, user=self.user
        )
        self.assertTrue(form.is_valid())
        account = form.save()
        self.user.refresh_from_db()
        self.assertEqual(account, self.account)
        self.assertEqual(self.user.first_name, "Janet")
        self.assertEqual(self.user.last_name, "Doe")
