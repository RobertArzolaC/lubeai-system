"""Shared test case for the tenancy apps.

Provisioning creates (and migrates) a real PostgreSQL schema, so each test that
exercises it needs a place to drop what it created. ``TenantTestCase`` already
provides a throwaway schema for the test itself; this base class adds the
helpers to provision and remove further tenants inside it.
"""

from __future__ import annotations

from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenancy import choices, models, services


class TenantProvisionTestCase(TenantTestCase):
    """Run tests inside a throwaway tenant and provision extra clients."""

    @classmethod
    def setup_tenant(cls, tenant: models.Tenant) -> None:
        """Fill the business fields ``Tenant`` requires before saving.

        Args:
            tenant: The throwaway tenant created by ``TenantTestCase``.
        """
        tenant.name = "Tenancy tests"
        tenant.slug = tenant.schema_name
        tenant.kind = choices.TenantKind.LAB

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
