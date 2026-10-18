"""Shared test case for the organizations app.

``Organization`` is a TENANT model: its table only exists inside a tenant
schema. Every test that touches it must therefore run with a tenant selected,
which is what :class:`~apps.core.tests.base.TenantSchemaTestCase` provides; this
module only keeps the app-specific name so the suite reads in the vocabulary of
the app under test.
"""

from __future__ import annotations

from apps.core.tests.base import TenantSchemaTestCase


class OrganizationTenantTestCase(TenantSchemaTestCase):
    """Run a test class inside an organization's own tenant schema.

    Tests build the ``Organization`` tree inside that schema, exactly as
    provisioning does in production.
    """
