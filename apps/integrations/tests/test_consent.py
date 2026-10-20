"""Tests for the OAuth consent and error pages."""

from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse
from django_tenants.test.client import TenantClient

from apps.integrations.tests.base import IntegrationTenantTestCase
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


class ConsentPageTests(IntegrationTenantTestCase):
    """Consent page content and CSRF protection."""

    def setUp(self) -> None:
        super().setUp()
        self.organization = organization_factories.OrganizationFactory()
        self.user = user_factories.UserFactory(organization=self.organization)
        self.grant_permissions(
            self.user,
            "equipment.view_machine",
            "reports.view_report",
            "alerts.view_alert",
        )
        self.oauth_client = self.create_oauth_client()
        self.params, self.verifier = self.authorize_params(self.oauth_client)
        self.url = reverse("django_mcpz_oauth:authorize")

    def test_consent_shows_role_based_access(self) -> None:
        """The page describes the modules the user can access."""
        self.client.force_login(self.user)
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Equipos y componentes")
        self.assertContains(response, "Reportes de laboratorio")
        self.assertContains(response, "Alertas y su estado")
        self.assertContains(response, self.organization.name)

    def test_consent_requires_csrf(self) -> None:
        """A forged POST without a CSRF token is rejected."""
        client = TenantClient(self.tenant, enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            f"{self.url}?{urlencode(self.params)}",
            {"decision": "allow"},
        )
        self.assertEqual(response.status_code, 403)

    def test_consent_accepts_valid_csrf(self) -> None:
        """The rendered form can be submitted with its CSRF cookie."""
        client = TenantClient(self.tenant, enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(self.url, self.params)
        token = client.cookies["csrftoken"].value
        response = client.post(
            f"{self.url}?{urlencode(self.params)}",
            {"decision": "allow"},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 302)

    def test_error_page_is_friendly(self) -> None:
        """Invalid clients get the Spanish error page."""
        params = dict(self.params)
        params["client_id"] = "unknown-client"
        self.client.force_login(self.user)
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "No se pudo completar la conexión", status_code=400
        )
        self.assertContains(response, "invalid_client", status_code=400)
