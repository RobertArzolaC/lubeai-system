"""Tests for the removal of the legacy ``Account`` model."""

import importlib

from django.test import TestCase

from apps.users import models as users_models


def _load_migration():
    """Import the data migration that removes the Account model."""
    return importlib.import_module("apps.users.migrations.0005_delete_account")


class AccountModelRemovedTests(TestCase):
    """The ``Account`` model no longer exists."""

    def test_account_model_is_gone(self) -> None:
        """The users app exposes no ``Account`` symbol."""
        self.assertFalse(hasattr(users_models, "Account"))

    def test_user_has_no_is_account(self) -> None:
        """``User.is_account`` was tied to the removed model."""
        self.assertFalse(hasattr(users_models.User, "is_account"))


class DeleteAccountMigrationTests(TestCase):
    """The data migration deactivates users whose account was removed."""

    def test_deactivates_removed_account_users(self) -> None:
        """Review Focus #2: removed accounts become inactive users."""

        class _FakeAccountManager:
            def filter(self, **kwargs):
                self.kwargs = kwargs
                return self

            def values_list(self, *args, **kwargs):
                return [1, 2]

        class _FakeAccount:
            objects = _FakeAccountManager()

        class _FakeUserManager:
            def filter(self, **kwargs):
                self.kwargs = kwargs
                return self

            def update(self, **kwargs):
                _FakeUserManager.last_update = kwargs
                return 2

        class _FakeUser:
            objects = _FakeUserManager()

        class _FakeApps:
            def get_model(self, app_label, model_name):
                return _FakeAccount if model_name == "Account" else _FakeUser

        migration = _load_migration()
        migration.deactivate_removed_account_users(_FakeApps(), None)

        self.assertEqual(_FakeUserManager.last_update, {"is_active": False})
