"""Tests for branding applied to the login template and the application shell.

Both pages are served from the tenant's own schema: ``TenantMainMiddleware``
resolves the host to a tenant, ``OrganizationMiddleware`` publishes the
organization in effect for the request and the branding context processor turns
it into the ``branding`` / ``current_organization`` / ``current_tenant``
template variables.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse

from apps.organizations import choices, models
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.users.factories import UserFactory


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


class ShellBrandingTests(OrganizationTenantTestCase):
    """The shell renders the branding of the organization in effect."""

    def setUp(self) -> None:
        """Give the tenant and one of its clients different brands."""
        super().setUp()
        self.tenant.name = "ACME"
        self.tenant.primary_color = "#123abc"
        self.tenant.save()
        self.organization = models.Organization.objects.create(
            name="Planta Norte",
            slug="planta-norte",
            kind=choices.OrganizationKind.FINAL,
            primary_color="#00ff00",
        )

    def shell_response(self, organization: models.Organization | None) -> HttpResponse:
        """Return the shell as a user of ``organization`` sees it.

        Args:
            organization: The organization the signed-in user belongs to, or
                ``None`` for a user without one.

        Returns:
            The rendered profile page (which extends the application shell).
        """
        self.client.force_login(UserFactory(organization=organization))
        response = self.client.get(reverse("apps.users:profile"))
        self.assertEqual(response.status_code, 200)
        return response

    def test_shell_shows_the_user_organization_brand(self) -> None:
        """The branding of the user's own organization wins over the tenant's."""
        response = self.shell_response(self.organization)

        self.assertContains(response, "--color-primary: #00ff00")
        self.assertContains(response, "Planta Norte")
        self.assertNotContains(response, "--color-primary: #123abc")

    def test_shell_falls_back_to_the_tenant_brand(self) -> None:
        """A user without an organization is branded by the tenant."""
        response = self.shell_response(None)

        self.assertContains(response, "--color-primary: #123abc")
        self.assertContains(response, "ACME")
        self.assertNotContains(response, "--color-primary: #00ff00")


class BrandFallbackRenderingTests(SimpleTestCase):
    """The brand fallbacks degrade instead of raising when there is no tenant.

    The filter argument of ``{{ a|default:b.c }}`` is resolved with
    ``ignore_failures=False``, so a missing ``b`` raises ``VariableDoesNotExist``
    (an HTTP 500) instead of falling back. The templates use ``{% firstof %}``,
    which tolerates the missing lookup.
    """

    def test_shell_header_renders_without_tenant(self) -> None:
        """The sidebar name renders with no organization and no tenant."""
        html = render_to_string("includes/aside.html")

        self.assertIn("<aside", html)

    def test_login_logo_alt_renders_without_tenant(self) -> None:
        """The login logo is still labelled when no tenant is in context."""
        branding = {"logo": SimpleNamespace(url="/media/tenant-logo.png")}

        html = render_to_string("account/login.html", {"branding": branding})

        self.assertIn('alt="Logo"', html)
        self.assertIn("/media/tenant-logo.png", html)
