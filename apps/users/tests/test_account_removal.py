"""Tests for the removal of the legacy ``Account`` model."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase

from apps.users import models as users_models
from apps.users.tests.base import UserTenantTestCase


class AccountModelRemovedTests(TestCase):
    """The ``Account`` model no longer exists."""

    def test_account_model_is_gone(self) -> None:
        """The users app exposes no ``Account`` symbol."""
        self.assertFalse(hasattr(users_models, "Account"))

    def test_user_has_no_is_account(self) -> None:
        """``User.is_account`` was tied to the removed model."""
        self.assertFalse(hasattr(users_models.User, "is_account"))


class DeleteAccountMigrationTests(UserTenantTestCase):
    """The data migration deactivates users whose account was removed.

    Runs the real migration executor inside the tenant schema so the
    ``RunPython`` operates on actual rows: an account flagged ``is_removed``
    must end as an inactive user, and a normal account must stay active
    (Review Focus #2).
    """

    migrate_from = [("users", "0004_role")]
    migrate_to = [("users", "0005_delete_account")]

    def _migrate(self, targets) -> None:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)

    def setUp(self) -> None:
        super().setUp()
        self._migrate(self.migrate_from)
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        user_model = old_apps.get_model("users", "User")
        account_model = old_apps.get_model("users", "Account")

        self.removed_user = user_model.objects.create(
            email="removed@example.com", password="x", is_active=True
        )
        self.kept_user = user_model.objects.create(
            email="kept@example.com", password="x", is_active=True
        )
        account_model.objects.create(user=self.removed_user, is_removed=True)
        account_model.objects.create(user=self.kept_user, is_removed=False)

        # The rows above leave foreign-key trigger events pending; inside the
        # transaction a test runs in, PostgreSQL refuses to drop a table with
        # pending trigger events. Draining them keeps the migration honest.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

        self._migrate(self.migrate_to)

    def tearDown(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_removed_account_user_is_deactivated(self) -> None:
        """A user whose account was removed becomes inactive."""
        user = users_models.User.objects.get(pk=self.removed_user.pk)
        self.assertFalse(user.is_active)

    def test_normal_account_user_stays_active(self) -> None:
        """A user with a live account is left untouched."""
        user = users_models.User.objects.get(pk=self.kept_user.pk)
        self.assertTrue(user.is_active)
