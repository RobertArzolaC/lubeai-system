"""Tests for branding applied to templates."""

from django.test import TestCase
from django.urls import reverse

from apps.organizations import choices, models


class LoginBrandingTests(TestCase):
    """The login page is branded with the resolved tenant."""

    def test_login_shows_tenant_name(self) -> None:
        """The MARCO tenant name appears in the login page title."""
        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MARCO Peruana")

    def test_login_shows_primary_color_variable(self) -> None:
        """A tenant's primary color is injected as a CSS variable."""
        models.Organization.objects.filter(slug="marco").update(
            primary_color="#123abc",
            kind=choices.OrganizationKind.LAB,
        )
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "--color-primary: #123abc")
