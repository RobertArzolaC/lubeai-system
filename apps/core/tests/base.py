"""Shared test base for the tenant-scoped apps.

Every business app (``users``, ``organizations``, ``equipment``, ``reports``,
``alerts``, ``dashboard``, ``core``) lives in ``TENANT_APPS``: its tables only
exist inside a tenant schema. Django's plain :class:`~django.test.TestCase`
runs against whichever schema the connection points at — ``public`` by default —
so a test that touches a business model must first select a tenant.

:class:`~django_tenants.test.cases.TenantTestCase` creates a throwaway tenant
(and migrates its schema) for the test class;
:class:`TenantSchemaTestCase` adds the project's conventions on top of it so the
per-app test bases and the migrated suites share one implementation.
"""

from __future__ import annotations

from django.test import modify_settings, override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.tenancy import choices
from apps.tenancy import models as tenancy_models


class TenantSchemaTestCase(TenantTestCase):
    """Run a test class inside its own throwaway tenant schema.

    The tenant created by the base class is the hard isolation boundary of the
    platform, so the tests exercise the models exactly where they live in
    production: inside a tenant schema whose ``search_path`` also reaches the
    ``public`` schema.

    A test class customizes the throwaway tenant through the
    :attr:`tenant_name` and :attr:`tenant_kind` attributes instead of
    reimplementing :meth:`setup_tenant`.
    """

    #: Display name given to the throwaway tenant.
    tenant_name = "Test tenant"

    #: Platform-client kind given to the throwaway tenant. The value reuses the
    #: organization kind strings, so a test can stand in for any client level.
    tenant_kind = choices.TenantKind.LAB

    @classmethod
    def setUpClass(cls) -> None:
        """Create the throwaway tenant and apply class-level test settings.

        ``TenantTestCase.setUpClass`` creates and migrates the schema instead of
        delegating to ``SimpleTestCase.setUpClass``, which also skips the
        class-level ``override_settings`` / ``modify_settings`` registered by
        the decorators of the same name (``save_options`` stores them on the
        class, and only ``SimpleTestCase.setUpClass`` enters them). Re-entering
        them here keeps decorators such as ``@override_settings(TEMPLATES=...)``
        or ``@override_settings(ROOT_URLCONF=...)`` meaningful, without pulling
        in the class-wide atomics and ``setUpTestData`` that a full
        ``super().setUpClass()`` would open.
        """
        super().setUpClass()
        if cls._overridden_settings:
            cls.enterClassContext(override_settings(**cls._overridden_settings))
        if cls._modified_settings:
            cls.enterClassContext(modify_settings(cls._modified_settings))

    @classmethod
    def setup_tenant(cls, tenant: tenancy_models.Tenant) -> None:
        """Fill the business fields ``Tenant`` requires before saving.

        Args:
            tenant: The throwaway tenant created by ``TenantTestCase``. Its
                ``schema_name`` is already set, so the slug mirrors it and the
                two stay consistent (``Tenant.save`` derives the schema name
                from the slug).
        """
        tenant.name = cls.tenant_name
        tenant.slug = tenant.schema_name
        tenant.kind = cls.tenant_kind

    def setUp(self) -> None:
        """Send client requests to the tenant's own domain.

        Subclasses overriding ``setUp`` must call ``super().setUp()``: otherwise
        ``self.client`` keeps talking to ``testserver`` and every request is
        answered with a 404 by ``TenantMainMiddleware``.
        """
        super().setUp()
        self.client = TenantClient(self.tenant)
