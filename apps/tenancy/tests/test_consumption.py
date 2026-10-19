"""Tests for the per-tenant consumption metrics.

Usage is measured on the tenant's own PostgreSQL schema, so the tests run
inside a throwaway tenant (``TenantProvisionTestCase``) and seed it through the
regular factories.
"""

from __future__ import annotations

from django.contrib import admin as django_admin
from django.db import connection

from apps.reports import factories as report_factories
from apps.tenancy import models, services
from apps.tenancy.admin import TenantAdmin
from apps.tenancy.tests.base import TenantProvisionTestCase
from apps.users import factories as user_factories


def create_registry_tenant(slug: str = "ghost", name: str = "Ghost") -> models.Tenant:
    """Create a registry row in ``public`` whose schema does not exist.

    The console and the graduation runbook both write the ``Tenant`` row before
    its schema is restored, which is exactly the state this helper reproduces.

    Args:
        slug: Tenant slug and (missing) schema name.
        name: Human-readable tenant name.

    Returns:
        The saved, schema-less tenant.
    """
    previous_tenant = connection.tenant
    connection.set_schema_to_public()
    try:
        tenant = models.Tenant(slug=slug, name=name)
        tenant.auto_create_schema = False
        tenant.save()
    finally:
        connection.set_tenant(previous_tenant)
    return tenant


class ConsumptionServiceTests(TenantProvisionTestCase):
    """Usage per tenant is measurable for billing."""

    def test_consumption_reports_bytes_and_rows(self) -> None:
        """Consumption returns a positive byte count for a seeded tenant."""
        report_factories.ReportFactory()

        data = services.TenantService.consumption(self.tenant)

        self.assertGreater(data["bytes"], 0)
        self.assertIn("reports", data)
        self.assertGreaterEqual(data["reports"], 1)

    def test_consumption_counts_business_models(self) -> None:
        """The four billable models are counted inside the tenant's schema."""
        report_factories.ReportFactory()
        user_factories.UserFactory()

        data = services.TenantService.consumption(self.tenant)

        self.assertEqual(data["schema_name"], self.tenant.schema_name)
        self.assertGreaterEqual(data["organizations"], 1)
        self.assertGreaterEqual(data["machines"], 1)
        self.assertGreaterEqual(data["reports"], 1)
        self.assertGreaterEqual(data["users"], 1)

    def test_rows_is_the_sum_of_the_counted_models(self) -> None:
        """``rows`` aggregates the billable rows so it stays deterministic."""
        report_factories.ReportFactory()
        user_factories.UserFactory()

        data = services.TenantService.consumption(self.tenant)

        expected = sum(data[key] for key in services.TenantService.COUNTED_MODELS)
        self.assertEqual(data["rows"], expected)

    def test_consumption_of_an_empty_schema_has_no_business_rows(self) -> None:
        """A freshly provisioned schema has storage but no billable rows."""
        data = services.TenantService.consumption(self.tenant)

        self.assertEqual(data["rows"], 0)
        self.assertGreaterEqual(data["bytes"], 0)

    def test_consumption_of_a_missing_schema_returns_zeros(self) -> None:
        """A registry row without a schema is measured as empty, not public.

        Counting under ``tenant_context`` would resolve the counted models
        against a non-existent schema (an error, or a silent read of the
        ``public`` tables of the same name), so the guard must return zeros.
        """
        ghost = create_registry_tenant()

        data = services.TenantService.consumption(ghost)

        self.assertEqual(data["schema_name"], "ghost")
        self.assertEqual(data["bytes"], 0)
        self.assertEqual(data["rows"], 0)
        for key in services.TenantService.COUNTED_MODELS:
            self.assertEqual(data[key], 0)


class TenantServiceActivationTests(TenantProvisionTestCase):
    """Suspending and activating a tenant writes to the registry."""

    def test_set_active_toggles_and_persists(self) -> None:
        """``set_active`` persists the flag on the public registry row."""
        services.TenantService.set_active(self.tenant, False)
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.is_active)

        services.TenantService.set_active(self.tenant, True)
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.is_active)


class TenantAdminUsageTests(TenantProvisionTestCase):
    """The admin change page exposes the measured usage."""

    def test_usage_summary_reports_bytes(self) -> None:
        """``usage_summary`` renders the byte and row counts of the tenant."""
        report_factories.ReportFactory()
        admin_instance = TenantAdmin(models.Tenant, django_admin.site)

        summary = admin_instance.usage_summary(self.tenant)

        self.assertIn("bytes", summary)
        self.assertIn("rows", summary)
