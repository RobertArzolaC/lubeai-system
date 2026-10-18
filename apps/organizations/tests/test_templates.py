"""Tests for branding applied to the login template."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from apps.organizations import choices, models
from apps.organizations.tests.base import OrganizationTenantTestCase


class LoginBrandingTests(OrganizationTenantTestCase):
    """The login template renders the branding of the request's organization.

    The branding is attached to the request by the tenancy middleware; these
    tests render the template with that request so they stay focused on how the
    branding variables reach the markup.
    """

    def setUp(self) -> None:
        """Create the tenant's root organization."""
        super().setUp()
        self.organization = models.Organization.objects.create(
            name="MARCO Peruana",
            slug="marco",
            kind=choices.OrganizationKind.LAB,
        )

    def _render_login(self) -> str:
        """Render the login template as the middleware would serve it."""
        request = RequestFactory().get(reverse("account_login"))
        request.organization = self.organization
        # Context processors expect the attributes the real middleware stack
        # would have attached to the request.
        request.session = {}
        request.user = AnonymousUser()
        return render_to_string("account/login.html", request=request)

    def test_login_shows_tenant_name(self) -> None:
        """The organization name appears in the login page title."""
        self.assertIn("MARCO Peruana", self._render_login())

    def test_login_shows_primary_color_variable(self) -> None:
        """A tenant's primary color is injected as a CSS variable."""
        self.organization.primary_color = "#123abc"
        self.organization.save(update_fields=["primary_color"])

        self.assertIn("--color-primary: #123abc", self._render_login())

    def test_login_page_renders_over_http(self) -> None:
        """The login view answers inside the tenant schema."""
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
