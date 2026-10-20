"""Shared helpers for the integrations tests."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from django.contrib.auth.models import Permission
from django.urls import reverse
from django_mcpz.oauth.models import AccessToken, Client, RefreshToken

from apps.core.tests.base import TenantSchemaTestCase


class IntegrationTenantTestCase(TenantSchemaTestCase):
    """Run integration tests inside a tenant schema."""

    tenant_name = "Integrations tests"

    def resource_url(self) -> str:
        """Return the canonical MCP URL for the test tenant."""
        return f"http://{self.tenant.get_primary_domain().domain}/mcp"

    def create_oauth_client(
        self,
        *,
        name: str = "ChatGPT",
        redirect_uri: str = "https://chatgpt.com/connector_platform_oauth_redirect",
    ) -> Client:
        """Create a dynamically registered OAuth client."""
        return Client.objects.create(
            client_id=secrets.token_urlsafe(24),
            kind=Client.Kind.REGISTERED,
            name=name,
            redirect_uris=[redirect_uri],
        )

    def create_tokens(
        self,
        *,
        user,
        client: Client,
        resource: str | None = None,
        scope: str = "",
        access_lifetime: timedelta = timedelta(hours=1),
        refresh_lifetime: timedelta = timedelta(days=90),
    ) -> tuple[AccessToken, str, RefreshToken, str]:
        """Create an access/refresh token pair for a user and client."""
        resource = resource or self.resource_url()
        access, access_value = AccessToken.create(
            lifetime=access_lifetime,
            client=client,
            user=user,
            resource=resource,
            scope=scope,
        )
        refresh, refresh_value = RefreshToken.create(
            lifetime=refresh_lifetime,
            client=client,
            user=user,
            resource=resource,
            scope=scope,
            access_token=access,
        )
        return access, access_value, refresh, refresh_value

    def grant_permissions(self, user, *labels: str) -> None:
        """Grant ``app_label.codename`` permissions to a user."""
        permissions = Permission.objects.filter(
            content_type__app_label__in={label.split(".")[0] for label in labels},
            codename__in={label.split(".")[1] for label in labels},
        )
        user.user_permissions.add(*permissions)

    @staticmethod
    def pkce_pair() -> tuple[str, str]:
        """Return a PKCE verifier and its S256 challenge."""
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    def authorize_params(
        self,
        client: Client,
        *,
        scope: str = "",
        state: str = "state-123",
    ) -> tuple[dict[str, str], str]:
        """Build the authorization query and return it with the verifier."""
        verifier, challenge = self.pkce_pair()
        params = {
            "client_id": client.client_id,
            "redirect_uri": client.redirect_uris[0],
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": self.resource_url(),
            "state": state,
            "scope": scope,
        }
        return params, verifier

    def get_consent(self, user, params: dict[str, str]):
        """Log in and fetch the consent page."""
        self.client.force_login(user)
        return self.client.get(reverse("django_mcpz_oauth:authorize"), params)

    def post_authorize(self, params: dict[str, str], *, decision: str = "allow"):
        """Post an allow/deny decision with the authorization query intact."""
        url = reverse("django_mcpz_oauth:authorize")
        return self.client.post(
            f"{url}?{urlencode(params)}",
            {"decision": decision},
        )

    def exchange_code(
        self,
        *,
        client: Client,
        code: str,
        verifier: str,
        redirect_uri: str | None = None,
    ):
        """Exchange an authorization code for tokens."""
        return self.client.post(
            reverse("django_mcpz_oauth:token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client.client_id,
                "redirect_uri": redirect_uri or client.redirect_uris[0],
                "code_verifier": verifier,
                "resource": self.resource_url(),
            },
        )

    def mcp_request(
        self,
        access_token: str,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        legacy: bool = False,
    ):
        """Send one JSON-RPC request to the MCP endpoint."""
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        headers: dict[str, str] = {
            "HTTP_AUTHORIZATION": f"Bearer {access_token}",
        }
        if not legacy:
            payload["params"].setdefault(
                "_meta",
                {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            )
            headers.update(
                {
                    "HTTP_MCP_PROTOCOL_VERSION": "2026-07-28",
                    "HTTP_MCP_METHOD": method,
                }
            )
            if method == "tools/call":
                headers["HTTP_MCP_NAME"] = payload["params"]["name"]
        return self.client.post(
            "/mcp",
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def mcp_tool_result(self, response) -> Any:
        """Return the structured result or text payload of a tool call."""
        body = response.json()
        result = body["result"]
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except json.JSONDecodeError:
                return content[0]["text"]
        return result

    @staticmethod
    def redirect_query(response) -> dict[str, list[str]]:
        """Parse the query string of a redirect response."""
        return parse_qs(urlsplit(response["Location"]).query)
