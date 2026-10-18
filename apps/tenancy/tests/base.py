"""Shared test case for the tenancy apps.

Provisioning creates (and migrates) a real PostgreSQL schema, so each test that
exercises it needs a place to drop what it created.
:class:`~apps.core.tests.base.TenantSchemaTestCase` already provides a throwaway
schema for the test itself; this base class adds the helpers to provision and
remove further tenants inside it.
"""

from __future__ import annotations

from django.db import connection

from apps.core.tests.base import TenantSchemaTestCase
from apps.tenancy import choices, models, services


class TenantProvisionTestCase(TenantSchemaTestCase):
    """Run tests inside a throwaway tenant and provision extra clients."""

    tenant_name = "Tenancy tests"

    def provision(self, **overrides: object) -> models.Tenant:
        """Provision a tenant and schedule its schema for removal.

        Args:
            **overrides: Fields forwarded to :func:`services.provision_tenant`.

        Returns:
            The provisioned tenant.
        """
        fields: dict[str, object] = {
            "slug": "acme",
            "name": "ACME",
            "kind": choices.TenantKind.INTERMEDIARY.value,
            "admin_email": "admin@acme.pe",
            "default_password": "Demo12345!",
        }
        fields.update(overrides)
        tenant = services.provision_tenant(**fields)  # type: ignore[arg-type]
        self.addCleanup(self.drop_tenant, tenant)
        return tenant

    @staticmethod
    def drop_tenant(tenant: models.Tenant) -> None:
        """Delete a provisioned tenant row and its schema.

        Args:
            tenant: The tenant to remove.
        """
        connection.set_schema_to_public()
        tenant.delete(force_drop=True)
