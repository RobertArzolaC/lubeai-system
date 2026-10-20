"""Tests for the per-tenant OAuth cleanup command."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from django_mcpz.oauth.models import AccessToken, Client, RefreshToken

from apps.tenancy.services import provision_tenant
from apps.tenancy.tests.base import TenantProvisionTestCase
from apps.users import factories as user_factories


class ClearMCPOAuthCommandTests(TenantProvisionTestCase):
    """Expired and revoked OAuth tokens are removed from every tenant."""

    def create_client(self, name: str = "Cleanup client") -> Client:
        """Create a registered client in the current schema."""
        return Client.objects.create(
            client_id=f"{name.lower().replace(' ', '-')}-{timezone.now().timestamp()}",
            kind=Client.Kind.REGISTERED,
            name=name,
            redirect_uris=["https://example.com/callback"],
        )

    def create_token_pair(self, user, client: Client, lifetime: timedelta):
        """Create an access/refresh pair with the given lifetime."""
        resource = f"http://{connection.tenant.get_primary_domain().domain}/mcp"
        access, _access_value = AccessToken.create(
            lifetime=lifetime,
            client=client,
            user=user,
            resource=resource,
            scope="",
        )
        refresh, _refresh_value = RefreshToken.create(
            lifetime=lifetime,
            client=client,
            user=user,
            resource=resource,
            scope="",
            access_token=access,
        )
        return access, refresh

    def test_cleanup_removes_expired_and_revoked_but_keeps_active(self) -> None:
        """Only expired/revoked rows are deleted in the current tenant."""
        user = user_factories.UserFactory()
        expired_client = self.create_client("Expired")
        expired_access, expired_refresh = self.create_token_pair(
            user, expired_client, timedelta(seconds=-1)
        )
        revoked_client = self.create_client("Revoked")
        revoked_access, revoked_refresh = self.create_token_pair(
            user, revoked_client, timedelta(days=1)
        )
        revoked_access.revoke()
        revoked_refresh.revoke()
        active_client = self.create_client("Active")
        active_access, active_refresh = self.create_token_pair(
            user, active_client, timedelta(days=1)
        )

        call_command("clear_mcp_oauth", stdout=StringIO())

        self.assertFalse(AccessToken.objects.filter(pk=expired_access.pk).exists())
        self.assertFalse(RefreshToken.objects.filter(pk=expired_refresh.pk).exists())
        self.assertFalse(AccessToken.objects.filter(pk=revoked_access.pk).exists())
        self.assertFalse(RefreshToken.objects.filter(pk=revoked_refresh.pk).exists())
        self.assertTrue(AccessToken.objects.filter(pk=active_access.pk).exists())
        self.assertTrue(RefreshToken.objects.filter(pk=active_refresh.pk).exists())
        self.assertEqual(connection.tenant.schema_name, self.tenant.schema_name)

    def test_cleanup_runs_in_other_tenants(self) -> None:
        """A second tenant's expired tokens are cleaned too."""
        other = provision_tenant(
            slug="cleanup-other",
            name="Cleanup other",
            kind="final",
            admin_email="admin@cleanup-other.pe",
            default_password="Demo12345!",
        )
        self.addCleanup(self.drop_tenant, other)
        user = user_factories.UserFactory()
        client = self.create_client("Other tenant")
        access, refresh = self.create_token_pair(user, client, timedelta(seconds=-1))

        connection.set_tenant(other)
        other_user = user_factories.UserFactory()
        other_client = self.create_client("Other tenant second")
        other_access, other_refresh = self.create_token_pair(
            other_user, other_client, timedelta(seconds=-1)
        )
        connection.set_tenant(self.tenant)

        call_command("clear_mcp_oauth", stdout=StringIO())

        self.assertFalse(AccessToken.objects.filter(pk=access.pk).exists())
        self.assertFalse(RefreshToken.objects.filter(pk=refresh.pk).exists())
        connection.set_tenant(other)
        self.assertFalse(AccessToken.objects.filter(pk=other_access.pk).exists())
        self.assertFalse(RefreshToken.objects.filter(pk=other_refresh.pk).exists())
