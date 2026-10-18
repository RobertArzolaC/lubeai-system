"""Shared test case for the organizations app.

``Organization`` is a TENANT model: its table only exists inside a tenant
schema. Every test that touches it must therefore run with a tenant selected,
which is what :class:`~django_tenants.test.cases.TenantTestCase` does.
"""

from __future__ import annotations

from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.organizations import choices
from apps.tenancy import models as tenancy_models


class OrganizationTenantTestCase(TenantTestCase):
    """Run a test class inside its own throwaway tenant schema.

    The tenant created by the base class is the hard isolation boundary of the
    platform. Tests build the ``Organization`` tree inside that schema, exactly
    as provisioning does in production.
    """

    @classmethod
    def setup_tenant(cls, tenant: tenancy_models.Tenant) -> None:
        """Fill the business fields ``Tenant`` requires before saving.

        Args:
            tenant: The throwaway tenant created by ``TenantTestCase``. Its
                ``schema_name`` is already set, so the slug mirrors it and the
                two stay consistent (``Tenant.save`` derives the schema name
                from the slug).
        """
        tenant.name = "Test tenant"
        tenant.slug = tenant.schema_name
        tenant.kind = choices.OrganizationKind.LAB

    def setUp(self) -> None:
        """Send client requests to the tenant's primary domain."""
        super().setUp()
        self.client = TenantClient(self.tenant)
