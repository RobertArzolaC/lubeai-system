"""Tests for the ``apps.alerts.tasks`` module.

Alert notifications are TENANT work: the ``alerts_alert`` table only exists
inside a tenant schema and two clients may each own an alert with the same
primary key. The tests below pin the contract that makes the fan-out safe — the
task never uses the worker's search path, it only runs for an *active* tenant,
and ``public`` never holds business data.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core import mail
from django.db import connection
from django.test import SimpleTestCase
from django.utils.module_loading import import_string
from django_tenants.utils import (
    get_public_schema_name,
    schema_context,
    tenant_context,
)
from tenant_schemas_celery.db_scheduler import TenantAwareDatabaseScheduler
from tenant_schemas_celery.task import TenantTask

from apps.alerts import factories as alert_factories
from apps.alerts import models as alert_models
from apps.alerts import tasks
from apps.alerts.tests.base import AlertTenantTestCase
from apps.organizations import choices as organization_choices
from apps.organizations import factories as organization_factories
from apps.tenancy import choices as tenancy_choices
from apps.tenancy import models as tenancy_models
from apps.users import factories as user_factories
from apps.users import models as user_models


def make_tenant(schema_name: str, *, is_active: bool = True) -> tenancy_models.Tenant:
    """Create — and migrate — a tenant with the given schema.

    Args:
        schema_name: PostgreSQL schema the tenant owns.
        is_active: Whether the tenant is served.

    Returns:
        The saved tenant. The connection is left on ``public``.
    """
    tenant = tenancy_models.Tenant(
        name=schema_name,
        slug=schema_name,
        kind=tenancy_choices.TenantKind.LAB,
        is_active=is_active,
    )
    tenant.save(verbosity=0)
    return tenant


class SendAlertNotificationsTaskTests(AlertTenantTestCase):
    """The notification task only ever runs inside the owning schema."""

    @classmethod
    def setUpClass(cls) -> None:
        """Add a second active tenant and an inactive one next to the fixture.

        A tenant row is created on ``public``; the extra schemas let the tests
        prove that the task fans out to the *active* tenants only.
        """
        super().setUpClass()
        connection.set_schema_to_public()
        cls.other_tenant = make_tenant("alerts_other")
        cls.inactive_tenant = make_tenant("alerts_off", is_active=False)
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls) -> None:
        """Drop the extra schemas and then the fixture one."""
        connection.set_schema_to_public()
        cls.inactive_tenant.delete(force_drop=True)
        cls.other_tenant.delete(force_drop=True)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        connection.set_tenant(self.tenant)
        mail.outbox.clear()
        self.alert, self.recipient = self.seed(self.tenant, dedup_key="own")
        self.other_alert, self.other_recipient = self.seed(
            self.other_tenant, dedup_key="other"
        )

    @staticmethod
    def seed(
        tenant: tenancy_models.Tenant, *, dedup_key: str
    ) -> tuple[alert_models.Alert, user_models.User]:
        """Create an organization, a notifiable alert and its recipient.

        Args:
            tenant: Tenant whose schema receives the rows.
            dedup_key: Alert deduplication key; also names the organization.

        Returns:
            The alert and the user allowed to be notified about it.
        """
        with tenant_context(tenant):
            organization = organization_factories.OrganizationFactory(
                slug=f"org-{dedup_key}",
                kind=organization_choices.OrganizationKind.LAB,
            )
            alert = alert_factories.AlertFactory(
                organization=organization, dedup_key=dedup_key
            )
            user = user_factories.UserFactory()
            user.organization = organization
            user.save(update_fields=["organization"])
            user.user_permissions.add(*Permission.objects.filter(codename="view_alert"))
        return alert, user

    def recipients(self) -> set[str]:
        """Return the email addresses the last send produced."""
        return {message.to[0] for message in mail.outbox}

    def test_notifies_only_the_owning_tenant(self) -> None:
        """Running for one tenant notifies its recipients and no others."""
        result = tasks.send_alert_notifications_task(
            [self.alert.pk], self.tenant.schema_name
        )

        self.assertEqual(set(result), {self.tenant.schema_name})
        self.assertIn(self.recipient.email, self.recipients())
        self.assertNotIn(self.other_recipient.email, self.recipients())

    def test_other_tenant_gets_only_its_own_notification(self) -> None:
        """A same-numbered alert of another tenant never reaches this one."""
        result = tasks.send_alert_notifications_task(
            [self.other_alert.pk], self.other_tenant.schema_name
        )

        self.assertEqual(set(result), {self.other_tenant.schema_name})
        self.assertIn(self.other_recipient.email, self.recipients())
        self.assertNotIn(self.recipient.email, self.recipients())

    def test_public_schema_is_never_notified(self) -> None:
        """The public schema is not a client, so it is refused explicitly."""
        result = tasks.send_alert_notifications_task(
            [self.alert.pk], get_public_schema_name()
        )

        self.assertEqual(result, {})
        self.assertEqual(mail.outbox, [])

    def test_inactive_tenant_is_skipped(self) -> None:
        """A tenant that is no longer served receives no notification."""
        result = tasks.send_alert_notifications_task(
            [self.alert.pk], self.inactive_tenant.schema_name
        )

        self.assertEqual(result, {})
        self.assertEqual(mail.outbox, [])

    def test_unknown_schema_is_ignored(self) -> None:
        """A schema that is not in the registry is never used as a fallback."""
        result = tasks.send_alert_notifications_task([self.alert.pk], "ghost_schema")

        self.assertEqual(result, {})
        self.assertEqual(mail.outbox, [])

    def test_defaults_to_the_dispatching_schema(self) -> None:
        """Without an explicit schema the task uses the one it was run in."""
        result = tasks.send_alert_notifications_task.apply(args=[[self.alert.pk]])

        self.assertEqual(set(result.get()), {self.tenant.schema_name})
        self.assertIn(self.recipient.email, self.recipients())
        self.assertNotIn(self.other_recipient.email, self.recipients())

    def test_alerts_stay_in_their_own_schema(self) -> None:
        """Each tenant's alerts live in its schema; ``public`` holds none."""
        with tenant_context(self.tenant):
            self.assertEqual(alert_models.Alert.objects.count(), 1)
        with tenant_context(self.other_tenant):
            self.assertEqual(alert_models.Alert.objects.count(), 1)
        with schema_context(get_public_schema_name()):
            # ``alerts`` is a TENANT app: its table is not even created in the
            # registry schema, so no business row can live there.
            self.assertNotIn(
                alert_models.Alert._meta.db_table,
                connection.introspection.table_names(),
            )


class TenantAwareCeleryConfigurationTests(SimpleTestCase):
    """The Celery app and the beat scheduler must be tenant-aware."""

    def test_celery_app_uses_tenant_tasks(self) -> None:
        """``config.celery`` builds the app with the tenant-aware task class."""
        from config.celery import app

        self.assertTrue(issubclass(app.Task, TenantTask))

    def test_beat_scheduler_is_tenant_aware(self) -> None:
        """``CELERY_BEAT_SCHEDULER`` resolves to the tenant-aware scheduler."""
        self.assertEqual(
            settings.CELERY_BEAT_SCHEDULER,
            "tenant_schemas_celery.db_scheduler.TenantAwareDatabaseScheduler",
        )

        from config.celery import app

        self.assertIs(
            import_string(app.conf.beat_scheduler), TenantAwareDatabaseScheduler
        )
