"""Tests for public-schema routing.

The platform answers on one subdomain per tenant and has no fallback tenant, so
the ``public`` schema is reachable only through its own urlconf: a host that
matches no ``Domain`` must answer 404 instead of landing on somebody else's
schema.
"""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase

from apps.tenancy import choices, models

TENANT_MIDDLEWARE = "django_tenants.middleware.main.TenantMainMiddleware"

# The landing page is served on the ``public`` schema, where there is no
# ``Domain`` to resolve the host with: the tests that render it skip the
# middleware that would demand one.
MIDDLEWARE_WITHOUT_TENANTS = [
    middleware for middleware in settings.MIDDLEWARE if middleware != TENANT_MIDDLEWARE
]


class PublicSchemaRoutingTests(TestCase):
    """The ``public`` schema is wired to its own, tenant-free urlconf."""

    def test_public_schema_uses_the_public_urlconf(self) -> None:
        """``PUBLIC_SCHEMA_URLCONF`` points at the landing page module."""
        self.assertEqual(settings.PUBLIC_SCHEMA_URLCONF, "config.urls_public")

    def test_tenant_middleware_is_the_first_one(self) -> None:
        """The schema must be selected before any other middleware runs."""
        self.assertEqual(settings.MIDDLEWARE[0], TENANT_MIDDLEWARE)


@override_settings(
    ROOT_URLCONF="config.urls_public",
    MIDDLEWARE=MIDDLEWARE_WITHOUT_TENANTS,
)
class PublicLandingTests(TestCase):
    """The landing page renders with only the SHARED ``public`` tables."""

    def test_landing_renders_without_tenant_tables(self) -> None:
        """No context processor or template touches a TENANT-only table."""
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "public/landing.html")
        self.assertNotIn("admin/", response.content.decode())


class TenantRoutingTestCase(TenantTestCase):
    """Run the routing tests inside their own throwaway tenant schema."""

    @classmethod
    def setup_tenant(cls, tenant: models.Tenant) -> None:
        """Fill the business fields ``Tenant`` requires before saving.

        Args:
            tenant: The throwaway tenant created by ``TenantTestCase``.
        """
        tenant.name = "Routing tenant"
        tenant.slug = tenant.schema_name
        tenant.kind = choices.TenantKind.LAB


class UnknownHostTests(TenantRoutingTestCase):
    """A host with no ``Domain`` row must never be served by a tenant."""

    def test_unknown_host_returns_404(self) -> None:
        """Review Focus #1: an unknown subdomain answers 404, not a tenant."""
        # The failed lookup leaves the connection on the public schema; put the
        # tenant back for the rest of the class.
        self.addCleanup(connection.set_tenant, self.tenant)

        with override_settings(ALLOWED_HOSTS=[self.domain.domain, "unknown.test.com"]):
            response = self.client.get("/", HTTP_HOST="unknown.test.com")

        self.assertEqual(response.status_code, 404)

    def test_known_host_still_resolves_its_tenant(self) -> None:
        """The tenant's own domain keeps being served."""
        with override_settings(ALLOWED_HOSTS=[self.domain.domain]):
            response = self.client.get(
                reverse("account_login"), HTTP_HOST=self.domain.domain
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.tenant, self.tenant)
