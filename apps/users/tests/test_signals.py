"""Tests for the ``apps.users.signals`` module."""

from unittest import mock

from django.test import TestCase

from apps.users import models as users_models
from apps.users import signals
from apps.users.factories import AccountFactory, UserFactory


class UserSignalsTests(TestCase):
    """Tests for the user/account post_save and post_delete signals."""

    def test_user_creation_creates_account(self) -> None:
        """Creating a user auto-creates a linked Account."""
        user = UserFactory()
        self.assertTrue(users_models.Account.objects.filter(user=user).exists())

    def test_user_update_does_not_create_second_account(self) -> None:
        """Updating a user does not duplicate its Account."""
        user = UserFactory()
        user.first_name = "Changed"
        user.save()
        self.assertEqual(users_models.Account.objects.filter(user=user).count(), 1)

    def test_remove_account_user_deletes_related_user(self) -> None:
        """The ``remove_account_user`` handler deletes the related user."""
        account = AccountFactory()
        with mock.patch.object(users_models.User, "delete") as mock_delete:
            signals.remove_account_user(sender=users_models.Account, instance=account)
        mock_delete.assert_called_once_with()
