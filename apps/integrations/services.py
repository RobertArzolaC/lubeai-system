"""Services for the integrations app.

OAuth tokens are owned by ``django_mcpz.oauth``; this module only builds the
user-facing connection view and revokes a user's tokens for one assistant.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from django.db import transaction
from django.utils import timezone
from django_mcpz.oauth.models import (
    AccessToken,
    AuthorizationCode,
    Client,
    RefreshToken,
)


@dataclass(frozen=True)
class MCPConnection:
    """A user-facing view of one assistant connected to this tenant."""

    client: Client
    client_name: str
    redirect_host: str
    connected_at: datetime
    expires_at: datetime
    active: bool


class MCPConnectionService:
    """List and revoke a user's OAuth connections for the current tenant."""

    def connections_for_user(self, user, resource: str) -> list[MCPConnection]:
        """Return the user's connections for ``resource`` grouped by client.

        Args:
            user: The authenticated user.
            resource: The canonical MCP server URL for the current tenant.

        Returns:
            Connections ordered by assistant name.
        """
        access_tokens = list(
            AccessToken.objects.filter(user=user, resource=resource).select_related(
                "client"
            )
        )
        refresh_tokens = list(
            RefreshToken.objects.filter(user=user, resource=resource).select_related(
                "client"
            )
        )
        if not access_tokens and not refresh_tokens:
            return []

        access_by_client: dict[int, list[AccessToken]] = defaultdict(list)
        refresh_by_client: dict[int, list[RefreshToken]] = defaultdict(list)
        clients: dict[int, Client] = {}
        for token in access_tokens:
            access_by_client[token.client_id].append(token)
            clients[token.client_id] = token.client
        for token in refresh_tokens:
            refresh_by_client[token.client_id].append(token)
            clients[token.client_id] = token.client

        connections: list[MCPConnection] = []
        for client_id, client in clients.items():
            access = access_by_client.get(client_id, [])
            refresh = refresh_by_client.get(client_id, [])
            valid_access = [token for token in access if token.is_valid]
            valid_refresh = [
                token for token in refresh if token.is_valid and token.used_at is None
            ]
            all_tokens = [*access, *refresh]
            expiry_candidates = [
                token.expires_at for token in (*valid_refresh, *valid_access)
            ] or [token.expires_at for token in all_tokens]
            redirect_uris = client.redirect_uris or [""]
            redirect_host = urlsplit(str(redirect_uris[0])).hostname or ""
            connections.append(
                MCPConnection(
                    client=client,
                    client_name=client.name or client.client_id,
                    redirect_host=redirect_host,
                    connected_at=min(token.created_at for token in all_tokens),
                    expires_at=max(expiry_candidates),
                    active=bool(valid_access or valid_refresh),
                )
            )

        return sorted(
            connections, key=lambda connection: connection.client_name.lower()
        )

    def disconnect(self, user, client_id: int) -> None:
        """Revoke every token and pending code for one user and client.

        Args:
            user: The authenticated user.
            client_id: Primary key of the OAuth client.

        Raises:
            Client.DoesNotExist: When the user has no tokens for that client.
        """
        client = Client.objects.get(pk=client_id)
        has_tokens = (
            AccessToken.objects.filter(user=user, client=client).exists()
            or RefreshToken.objects.filter(user=user, client=client).exists()
        )
        if not has_tokens:
            raise Client.DoesNotExist

        now = timezone.now()
        with transaction.atomic():
            AccessToken.objects.filter(
                user=user, client=client, revoked_at__isnull=True
            ).update(revoked_at=now)
            RefreshToken.objects.filter(
                user=user, client=client, revoked_at__isnull=True
            ).update(revoked_at=now)
            AuthorizationCode.objects.filter(
                user=user, client=client, used_at__isnull=True
            ).update(used_at=now)
