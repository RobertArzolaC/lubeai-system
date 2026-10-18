"""Tests for branding applied to the login template.

The login page is served from the tenant's own schema: ``TenantMainMiddleware``
resolves the host to a tenant and the branding context processor turns that
tenant into the ``branding`` / ``current_tenant`` template variables.
"""

from __future__ import annotations

from django.urls import reverse

from apps.organizations.tests.base import OrganizationTenantTestCase


class LoginBrandingTests(OrganizationTenantTestCase):
    """The login template renders the branding of the request's tenant."""

    def setUp(self) -> None:
        """Give the tenant the brand the login page must show."""
        super().setUp()
        self.tenant.name = "MARCO Peruana"
        self.tenant.primary_color = "#123abc"
        self.tenant.save()

    def test_login_shows_tenant_name(self) -> None:
        """The tenant name reaches the login page title."""
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MARCO Peruana")

    def test_login_shows_primary_color_variable(self) -> None:
        """The tenant's primary color is injected as a CSS variable."""
        response = self.client.get(reverse("account_login"))

        self.assertContains(response, "--color-primary: #123abc")

    def test_login_page_renders_over_http(self) -> None:
        """The login view answers inside the tenant schema."""
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
