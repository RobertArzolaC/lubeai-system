"""Tests for the login page's OAuth context."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlsplit

from django.urls import reverse

from apps.integrations.tests.base import IntegrationTenantTestCase
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


class LoginContextTests(IntegrationTenantTestCase):
    """The login page must preserve the OAuth ``next`` URL."""

    def test_oauth_next_shows_context_and_hidden_field(self) -> None:
        """The login form explains the connection and keeps ``next``."""
        next_url = "/oauth/authorize?client_id=test&response_type=code"
        response = self.client.get("/", {"next": next_url})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inicia sesión para conectar tu asistente")
        self.assertContains(response, 'name="next"')
        self.assertContains(
            response, "oauth/authorize?client_id=test&amp;response_type=code"
        )

    def test_login_redirects_back_to_the_authorization_page(self) -> None:
        """After login the browser resumes the OAuth authorization request."""
        organization = organization_factories.OrganizationFactory()
        user = user_factories.UserFactory(organization=organization)
        oauth_client = self.create_oauth_client()
        params, _verifier = self.authorize_params(oauth_client)
        authorize_url = reverse("django_mcpz_oauth:authorize") + "?" + urlencode(params)
        response = self.client.get(authorize_url)
        self.assertEqual(response.status_code, 302)
        next_url = parse_qs(urlsplit(response["Location"]).query)["next"][0]
        response = self.client.post(
            "/",
            {
                "login": user.email,
                "password": "Passw0rd!123",
                "next": next_url,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/oauth/authorize"))

    def test_signup_link_is_hidden(self) -> None:
        """Self-registration is disabled, so the signup link is not shown."""
        response = self.client.get("/")
        self.assertNotContains(response, "Sign Up")
        self.assertContains(response, "Contacta al administrador")
