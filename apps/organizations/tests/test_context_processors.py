"""Tests for the branding context processor.

Branding is resolved per request: ``request.tenant`` (written by
``TenantMainMiddleware`` from the ``public`` schema) is the platform client's
brand, and ``request.organization`` (written by ``OrganizationMiddleware``) is
the organization **in effect**: the user's own node when it has one, otherwise
the tenant itself, which stands in for the root organization of its tree.
"""

from __future__ import annotations

from typing import Any

from django.test import RequestFactory
from django.urls import reverse

from apps.organizations import choices, constants, context_processors, models
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.tenancy import choices as tenancy_choices
from apps.users.factories import UserFactory


class BrandingTenantTests(OrganizationTenantTestCase):
    """Branding resolves from the request tenant inside the tenant schema."""

    def setUp(self) -> None:
        """Give the tenant a distinguishable brand and kind."""
        super().setUp()
        self.tenant.name = "ACME"
        self.tenant.kind = tenancy_choices.TenantKind.LAB
        self.tenant.primary_color = "#123abc"
        self.tenant.chart_danger = "#ff0000"
        self.tenant.capabilities = {}
        self.tenant.save()

    def branding_context(self) -> dict[str, Any]:
        """Return the context the processor builds for a real tenant request."""
        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        return context_processors.branding(response.wsgi_request)

    def test_branding_falls_back_to_tenant_defaults(self) -> None:
        """With no user organization in context the tenant brand is used."""
        context = self.branding_context()

        self.assertEqual(context["current_tenant"], self.tenant)
        # The tenant stands in for the root organization of its own tree.
        self.assertEqual(context["current_organization"], self.tenant)
        self.assertEqual(context["branding"]["primary_color"], "#123abc")
        self.assertEqual(context["branding"]["chart_danger"], "#ff0000")
        self.assertFalse(context["branding"]["logo"])
        # Slots the tenant leaves empty keep the platform default.
        self.assertEqual(
            context["branding"]["chart_info"],
            constants.DEFAULT_BRANDING["chart_info"],
        )

    def test_capabilities_default_from_the_tenant_kind(self) -> None:
        """A lab tenant gets the capabilities of the lab kind."""
        context = self.branding_context()

        self.assertTrue(context["capabilities"]["thresholds"])
        self.assertTrue(context["capabilities"]["analysis"])
        self.assertFalse(context["capabilities"]["labs"])
        self.assertFalse(context["show_labs"])
        self.assertFalse(context["show_fleet"])

    def test_tenant_capabilities_override_the_kind_defaults(self) -> None:
        """A per-tenant override wins over the kind default."""
        self.tenant.capabilities = {"labs": True}
        self.tenant.save()

        context = self.branding_context()

        self.assertTrue(context["show_labs"])
        self.assertFalse(context["show_fleet"])

    def test_branding_prefers_the_user_organization(self) -> None:
        """The organization in effect overrides the tenant brand."""
        organization = models.Organization.objects.create(
            name="Planta Norte",
            slug="planta-norte",
            kind=choices.OrganizationKind.FINAL,
            primary_color="#00ff00",
        )
        self.client.force_login(UserFactory(organization=organization))

        response = self.client.get(reverse("apps.users:profile"))
        context = context_processors.branding(response.wsgi_request)

        self.assertEqual(context["current_organization"], organization)
        self.assertEqual(context["current_tenant"], self.tenant)
        self.assertEqual(context["branding"]["primary_color"], "#00ff00")
        # The final-client kind also overrides the tenant's capabilities.
        self.assertFalse(context["capabilities"]["thresholds"])

    def test_branding_degrades_to_defaults_without_tenant(self) -> None:
        """A request outside any tenant still renders the default brand."""
        request = RequestFactory().get("/")

        context = context_processors.branding(request)

        self.assertIsNone(context["current_tenant"])
        self.assertIsNone(context["current_organization"])
        self.assertEqual(
            context["branding"]["primary_color"],
            constants.DEFAULT_BRANDING["primary_color"],
        )
        self.assertFalse(context["branding"]["logo"])
        self.assertEqual(context["capabilities"], {})
        self.assertFalse(context["show_labs"])
        self.assertFalse(context["show_fleet"])
