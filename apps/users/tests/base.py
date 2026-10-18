"""Shared test case for the users app.

``users`` is a TENANT app: its tables — and the ``auth`` tables it depends on —
only exist inside a tenant schema. Every test that touches the database must
therefore run with a tenant selected, which is what
:class:`~apps.core.tests.base.TenantSchemaTestCase` provides; this module only
keeps the app-specific name so the suite reads in the vocabulary of the app
under test.
"""

from __future__ import annotations

from apps.core.tests.base import TenantSchemaTestCase


class UserTenantTestCase(TenantSchemaTestCase):
    """Run a test class inside a tenant schema of its own.

    The tests exercise users (and the roles that group them) exactly where they
    live in production.
    """
