"""Tests for the connected assistants page."""

from __future__ import annotations

from datetime import timedelta

from django.urls import reverse

from apps.integrations.tests.base import IntegrationTenantTestCase
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


class ConnectedAppsTests(IntegrationTenantTestCase):
    """List and revoke the current user's OAuth connections."""

    def setUp(self) -> None:
        super().setUp()
        self.organization = organization_factories.OrganizationFactory()
        self.user = user_factories.UserFactory(organization=self.organization)
        self.client_record = self.create_oauth_client(name="ChatGPT")
        self.access, _access_value, self.refresh, _refresh_value = self.create_tokens(
            user=self.user, client=self.client_record
        )
        self.url = reverse("apps.integrations:connected_apps")

    def test_page_requires_login(self) -> None:
        """Anonymous users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_page_lists_own_connection(self) -> None:
        """The user's assistant appears with the tenant MCP URL."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ChatGPT")
        self.assertContains(response, self.resource_url())
        self.assertContains(response, "Desconectar")

    def test_page_does_not_list_another_user_connection(self) -> None:
        """Another user's tokens are never rendered."""
        other_user = user_factories.UserFactory(organization=self.organization)
        other_client = self.create_oauth_client(name="Other assistant")
        self.create_tokens(user=other_user, client=other_client)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "ChatGPT")
        self.assertNotContains(response, "Other assistant")

    def test_disconnect_revokes_tokens_and_codes(self) -> None:
        """Disconnecting revokes access and refresh tokens."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "apps.integrations:disconnect_app",
                kwargs={"pk": self.client_record.pk},
            )
        )
        self.assertRedirects(response, self.url)
        self.access.refresh_from_db()
        self.refresh.refresh_from_db()
        self.assertIsNotNone(self.access.revoked_at)
        self.assertIsNotNone(self.refresh.revoked_at)

    def test_disconnect_other_user_connection_is_404(self) -> None:
        """A user cannot disconnect a client they never authorized."""
        other_user = user_factories.UserFactory(organization=self.organization)
        other_client = self.create_oauth_client(name="Other assistant")
        self.create_tokens(user=other_user, client=other_client)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "apps.integrations:disconnect_app",
                kwargs={"pk": other_client.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_expired_connection_is_inactive(self) -> None:
        """Expired access and refresh tokens render as inactive."""
        client = self.create_oauth_client(name="Expired assistant")
        self.create_tokens(
            user=self.user,
            client=client,
            access_lifetime=timedelta(seconds=-1),
            refresh_lifetime=timedelta(seconds=-1),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Expired assistant")
        connection = next(
            item
            for item in response.context["connections"]
            if item.client_name == "Expired assistant"
        )
        self.assertFalse(connection.active)

    def test_revoked_connection_is_listed_as_inactive(self) -> None:
        """Revoked tokens remain visible so the user can audit the client."""
        client = self.create_oauth_client(name="Revoked assistant")
        access, _access_value, refresh, _refresh_value = self.create_tokens(
            user=self.user, client=client
        )
        access.revoke()
        refresh.revoke()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Revoked assistant")
        connection = next(
            item
            for item in response.context["connections"]
            if item.client_name == "Revoked assistant"
        )
        self.assertFalse(connection.active)

    def test_page_uses_no_store_cache(self) -> None:
        """The connection page is not cached by intermediaries."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn("no-store", response["Cache-Control"])

    def test_page_renders_verified_provider_steps(self) -> None:
        """The page shows the current menu path for each provider."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Complementos")
        self.assertContains(response, "Agregar servidor MCP personalizado")
        self.assertContains(response, "Agregar conector personalizado")
        self.assertContains(response, "Inteligencia Personalizada")
        self.assertContains(response, "Personalizado")

    def test_page_renders_copyable_server_identity(self) -> None:
        """The suggested name and description are ready to copy."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "LubeAI")
        self.assertContains(
            response, "Consulta de equipos, reportes y alertas de lubricación."
        )

    def test_page_renders_guides_without_organization(self) -> None:
        """Users without an organization still see the steps and the warning."""
        user = user_factories.UserFactory(organization=None)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, "no tiene una organización asignada")
        self.assertContains(response, "Agregar servidor MCP personalizado")
