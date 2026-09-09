"""Tests for the ``apps.users.models`` module."""

from allauth.account.models import EmailAddress
from django.db import IntegrityError
from django.test import TestCase

from apps.users import models as users_models
from apps.users.factories import AccountFactory, UserFactory


class UserModelTests(TestCase):
    """Tests for the :class:`users_models.User` model."""

    def setUp(self) -> None:
        self.user = UserFactory(
            email="jane.doe@example.com",
            first_name="Jane",
            last_name="Doe",
        )

    def test_user_str_returns_email(self) -> None:
        """The string representation of a user is its email."""
        self.assertEqual(str(self.user), "jane.doe@example.com")

    def test_full_name_combines_first_and_last(self) -> None:
        """``full_name`` joins first and last names."""
        self.assertEqual(self.user.full_name, "Jane Doe")

    def test_is_account_true_when_account_exists(self) -> None:
        """A user that has an account reports ``is_account`` as True."""
        self.assertTrue(hasattr(self.user, "account"))
        self.assertTrue(self.user.is_account)

    def test_is_email_verified_false_by_default(self) -> None:
        """An unverified email address makes ``is_email_verified`` False."""
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=False
        )
        self.assertFalse(self.user.account.is_email_verified)

    def test_is_email_verified_true_when_verified(self) -> None:
        """A verified email address makes ``is_email_verified`` True."""
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )
        self.assertTrue(self.user.account.is_email_verified)

    def test_user_cannot_have_duplicate_email(self) -> None:
        """Creating two users with the same email raises IntegrityError."""
        with self.assertRaises(IntegrityError):
            UserFactory(email="jane.doe@example.com")

    def test_soft_delete_account_does_not_delete_user(self) -> None:
        """Soft deleting an Account keeps the related user active."""
        account = self.user.account
        account.delete()
        self.assertTrue(account.is_removed)
        self.assertFalse(users_models.Account.objects.filter(pk=account.pk).exists())
        self.assertTrue(users_models.User.objects.filter(pk=self.user.pk).exists())


class AccountModelTests(TestCase):
    """Tests for the :class:`users_models.Account` model."""

    def setUp(self) -> None:
        self.account = AccountFactory()

    def test_account_str_returns_user_full_name(self) -> None:
        """The string representation is the linked user full name."""
        user = self.account.user
        self.assertEqual(str(self.account), user.get_full_name())

    def test_account_full_name_property(self) -> None:
        """``full_name`` mirrors the user's full name."""
        self.assertEqual(self.account.full_name, self.account.user.get_full_name())

    def test_account_meta_ordering(self) -> None:
        """Accounts are ordered by user last/first name by default."""
        self.assertEqual(
            users_models.Account._meta.ordering,
            ("user__last_name", "user__first_name"),
        )
