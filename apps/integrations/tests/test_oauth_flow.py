"""End-to-end tests for the MCP OAuth flow and protocol."""

from __future__ import annotations

import json
from datetime import timedelta

from django.db import connection
from django.urls import reverse
from django_mcpz.oauth.models import Client
from django_tenants.test.client import TenantClient

from apps.alerts import factories as alert_factories
from apps.equipment import factories as equipment_factories
from apps.integrations.tests.base import IntegrationTenantTestCase
from apps.organizations import factories as organization_factories
from apps.reports import factories as report_factories
from apps.tenancy.services import provision_tenant
from apps.users import factories as user_factories


class OAuthDiscoveryTests(IntegrationTenantTestCase):
    """Discovery documents must describe this tenant's URLs."""

    def test_protected_resource_metadata(self) -> None:
        """The resource document names the tenant MCP URL and issuer."""
        response = self.client.get("/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resource"], self.resource_url())
        self.assertEqual(
            payload["authorization_servers"],
            [f"http://{self.tenant.get_primary_domain().domain}/oauth"],
        )
        self.assertEqual(payload["resource_name"], "LubeAI")

    def test_authorization_server_metadata(self) -> None:
        """The authorization server document lists the OAuth endpoints."""
        response = self.client.get("/.well-known/oauth-authorization-server/oauth")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["issuer"],
            f"http://{self.tenant.get_primary_domain().domain}/oauth",
        )
        self.assertTrue(payload["authorization_endpoint"].endswith("/oauth/authorize"))
        self.assertTrue(payload["token_endpoint"].endswith("/oauth/token"))
        self.assertTrue(payload["registration_endpoint"].endswith("/oauth/register"))

    def test_dynamic_registration(self) -> None:
        """A hosted assistant can register itself dynamically."""
        response = self.client.post(
            "/oauth/register",
            data=json.dumps(
                {
                    "client_name": "ChatGPT",
                    "redirect_uris": [
                        "https://chatgpt.com/connector_platform_oauth_redirect"
                    ],
                    "token_endpoint_auth_method": "none",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["client_id"])
        self.assertEqual(payload["client_name"], "ChatGPT")
        self.assertEqual(payload["token_endpoint_auth_method"], "none")


class OAuthFlowTests(IntegrationTenantTestCase):
    """Authorization code + PKCE, refresh, revoke and MCP calls."""

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
        self.machine = equipment_factories.MachineFactory(
            organization=self.organization,
            branch__organization=self.organization,
        )
        self.component = equipment_factories.ComponentFactory(
            machine=self.machine,
            type__organization=self.organization,
        )
        self.report = report_factories.ReportFactory(
            machine=self.machine,
            component=self.component,
            organization=self.organization,
        )
        self.alert = alert_factories.AlertFactory(
            machine=self.machine,
            component=self.component,
            report=self.report,
            organization=self.organization,
        )

    def issue_tokens(
        self,
        *,
        client: Client | None = None,
        user=None,
        scope: str = "",
    ) -> tuple[Client, str, str]:
        """Run the browser consent flow and return access/refresh tokens."""
        client = client or self.create_oauth_client()
        user = user or self.user
        params, verifier = self.authorize_params(client, scope=scope)
        self.client.force_login(user)
        consent = self.client.get(reverse("django_mcpz_oauth:authorize"), params)
        self.assertEqual(consent.status_code, 200, consent.content)
        redirect = self.post_authorize(params)
        self.assertEqual(redirect.status_code, 302, redirect.content)
        code = self.redirect_query(redirect)["code"][0]
        token_response = self.exchange_code(client=client, code=code, verifier=verifier)
        self.assertEqual(token_response.status_code, 200, token_response.content)
        payload = token_response.json()
        return client, payload["access_token"], payload["refresh_token"]

    def test_authorize_requires_login(self) -> None:
        """Anonymous visitors are sent to the tenant login with a next URL."""
        client = self.create_oauth_client()
        params, _verifier = self.authorize_params(client)
        response = self.client.get(reverse("django_mcpz_oauth:authorize"), params)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/?next=", response["Location"])

    def test_consent_page_is_branded_and_spanish(self) -> None:
        """The consent page explains the access in Spanish."""
        client = self.create_oauth_client()
        params, _verifier = self.authorize_params(client)
        self.client.force_login(self.user)
        response = self.client.get(reverse("django_mcpz_oauth:authorize"), params)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "django_mcpz/oauth/authorize.html")
        self.assertContains(response, "ChatGPT")
        self.assertContains(response, "Permitir acceso")
        self.assertContains(response, "Cancelar")
        self.assertContains(response, self.organization.name)
        self.assertNotContains(response, "Requested scope")

    def test_allow_creates_authorization_code(self) -> None:
        """Allowing access redirects to the client with a code and state."""
        client = self.create_oauth_client()
        params, _verifier = self.authorize_params(client)
        self.client.force_login(self.user)
        response = self.post_authorize(params)
        self.assertEqual(response.status_code, 302)
        query = self.redirect_query(response)
        self.assertIn("code", query)
        self.assertEqual(query["state"], ["state-123"])

    def test_deny_redirects_with_access_denied(self) -> None:
        """Denying access redirects with the OAuth error."""
        client = self.create_oauth_client()
        params, _verifier = self.authorize_params(client)
        self.client.force_login(self.user)
        response = self.post_authorize(params, decision="deny")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.redirect_query(response)["error"], ["access_denied"])

    def test_invalid_redirect_uri_shows_error_page(self) -> None:
        """An unregistered redirect URI is rejected before consent."""
        client = self.create_oauth_client(
            redirect_uri="https://chatgpt.com/connector_platform_oauth_redirect"
        )
        params, _verifier = self.authorize_params(client)
        params["redirect_uri"] = "https://evil.example/callback"
        self.client.force_login(self.user)
        response = self.client.get(reverse("django_mcpz_oauth:authorize"), params)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "django_mcpz/oauth/error.html")

    def test_token_exchange_and_tool_calls(self) -> None:
        """A token obtained through OAuth can list and call tools."""
        _client, access_token, _refresh_token = self.issue_tokens()
        response = self.mcp_request(access_token, "tools/list")
        self.assertEqual(response.status_code, 200, response.content)
        names = {tool["name"] for tool in response.json()["result"]["tools"]}
        self.assertIn("list_equipment", names)
        self.assertIn("list_reports", names)
        self.assertIn("list_alerts", names)

        response = self.mcp_request(
            access_token,
            "tools/call",
            {"name": "list_equipment", "arguments": {}},
        )
        self.assertEqual(response.status_code, 200, response.content)
        result = self.mcp_tool_result(response)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["name"], self.machine.name)

    def test_refresh_token_rotates(self) -> None:
        """A refresh token issues a new access token."""
        client, _access_token, refresh_token = self.issue_tokens()
        response = self.client.post(
            reverse("django_mcpz_oauth:token"),
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client.client_id,
                "resource": self.resource_url(),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["access_token"])
        self.assertNotEqual(payload["refresh_token"], refresh_token)

    def test_revoke_cuts_access(self) -> None:
        """Revoking the refresh token also revokes the access token."""
        client, access_token, refresh_token = self.issue_tokens()
        response = self.client.post(
            reverse("django_mcpz_oauth:revoke"),
            {"token": refresh_token, "client_id": client.client_id},
        )
        self.assertEqual(response.status_code, 200)
        response = self.mcp_request(access_token, "tools/list")
        self.assertEqual(response.status_code, 401)

    def test_unauthorized_challenge_points_at_metadata(self) -> None:
        """Without a token the server returns the OAuth challenge."""
        response = self.client.post(
            "/mcp",
            data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("resource_metadata=", response.headers["WWW-Authenticate"])

    def test_token_is_bound_to_the_tenant_host(self) -> None:
        """A token issued for another resource is rejected here."""
        client = self.create_oauth_client()
        _access, access_value, _refresh, _refresh_value = self.create_tokens(
            user=self.user,
            client=client,
            resource="http://other.test.com/mcp",
        )
        response = self.mcp_request(access_value, "tools/list")
        self.assertEqual(response.status_code, 401)

    def test_token_from_tenant_a_is_rejected_on_tenant_b(self) -> None:
        """A token issued in one schema does not authenticate in another."""
        client = self.create_oauth_client()
        _access, access_value, _refresh, _refresh_value = self.create_tokens(
            user=self.user, client=client
        )
        other = provision_tenant(
            slug="cross-tenant-other",
            name="Cross tenant other",
            kind="final",
            admin_email="admin@cross-tenant.pe",
            default_password="Demo12345!",
        )
        self.addCleanup(self._drop_tenant, other)

        response = TenantClient(other).post(
            "/mcp",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        }
                    },
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_value}",
            HTTP_MCP_PROTOCOL_VERSION="2026-07-28",
            HTTP_MCP_METHOD="tools/list",
        )
        self.assertEqual(response.status_code, 401, response.content)

    def _drop_tenant(self, tenant) -> None:
        """Drop a tenant schema provisioned by one test."""
        connection.set_schema_to_public()
        tenant.delete(force_drop=True)
        connection.set_tenant(self.tenant)

    def test_expired_token_is_rejected(self) -> None:
        """Expired access tokens are rejected."""
        client = self.create_oauth_client()
        _access, access_value, _refresh, _refresh_value = self.create_tokens(
            user=self.user,
            client=client,
            access_lifetime=timedelta(seconds=-1),
        )
        response = self.mcp_request(access_value, "tools/list")
        self.assertEqual(response.status_code, 401)

    def test_revoked_token_is_rejected(self) -> None:
        """Revoked access tokens are rejected."""
        client = self.create_oauth_client()
        access, access_value, _refresh, _refresh_value = self.create_tokens(
            user=self.user,
            client=client,
        )
        access.revoke()
        response = self.mcp_request(access_value, "tools/list")
        self.assertEqual(response.status_code, 401)

    def test_legacy_protocol_initialize_and_tools(self) -> None:
        """Clients on the 2025 stateless protocol still work."""
        _client, access_token, _refresh_token = self.issue_tokens()
        response = self.mcp_request(
            access_token,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
            legacy=True,
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = self.mcp_request(access_token, "tools/list", legacy=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["result"]["tools"])
