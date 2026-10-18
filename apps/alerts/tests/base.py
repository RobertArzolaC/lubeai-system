"""Shared test case for the alerts app.

``alerts`` is a TENANT app: its tables — and the ``equipment``/``reports``/
``organizations`` tables it references — only exist inside a tenant schema.
Every test that touches the database must therefore run with a tenant selected,
which is what :class:`~apps.core.tests.base.TenantSchemaTestCase` provides; this
module only keeps the app-specific name so the suite reads in the vocabulary of
the app under test.
"""

from __future__ import annotations

from apps.core.tests.base import TenantSchemaTestCase


class AlertTenantTestCase(TenantSchemaTestCase):
    """Run a test class inside an alert's own tenant schema.

    The alert rows a test builds live exactly where they live in production.
    """
