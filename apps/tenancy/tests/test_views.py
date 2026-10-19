"""Tests for the platform's tenant console.

The console lives in the operations tenant (``ops``), so most tests run inside a
throwaway tenant whose schema is named ``ops``. Registry rows are created in the
``public`` schema on purpose: only ``public`` may write them, which mirrors how
provisioning behaves in production.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

from django.contrib.auth.models import Permission
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from apps.tenancy import choices, constants, models
from apps.tenancy.tests.base import TenantProvisionTestCase
from apps.users.factories import UserFactory


def grant(user: Any, *codenames: str) -> None:
    """Grant the given ``tenancy`` permission codenames to ``user``.

    Args:
        user: The user receiving the permissions.
        *codenames: Permission codenames of the ``tenancy`` app.
    """
    permissions = Permission.objects.filter(
        content_type__app_label="tenancy", codename__in=codenames
    )
    user.user_permissions.add(*permissions)


def make_registry_tenant(slug: str, name: str, kind: str = "final") -> models.Tenant:
    """Create a registry row in ``public`` without creating a schema.

    Only the ``public`` schema may persist a tenant, so the connection is
    switched for the write and restored afterwards. Skipping the schema keeps
    the tests that only exercise the console fast.

    Args:
        slug: Tenant slug and schema name.
        name: Human-readable tenant name.
        kind: Tenant kind.

    Returns:
        The saved tenant.
    """
    previous_tenant = connection.tenant
    connection.set_schema_to_public()
    try:
        tenant = models.Tenant(slug=slug, name=name, kind=kind)
        tenant.auto_create_schema = False
        tenant.save()
    finally:
        connection.set_tenant(previous_tenant)
    return tenant


class OpsTenantTestCase(TenantProvisionTestCase):
    """Run inside a throwaway tenant whose schema is the operations one."""

    tenant_name = "Operations"
    tenant_kind = choices.TenantKind.PLATFORM

    @classmethod
    def get_test_schema_name(cls) -> str:
        """Name the throwaway schema ``ops`` so it is the operations tenant."""
        return constants.OPS_TENANT_SLUG


class TenantListViewTests(OpsTenantTestCase):
    """Listing and filtering the registry from the operations tenant."""

    def setUp(self) -> None:
        """Create a client and sign in an operator."""
        super().setUp()
        self.acme = make_registry_tenant("acme", "ACME", kind="lab")
        self.user = UserFactory()

    def test_list_requires_permission(self) -> None:
        """An authenticated operator without the permission is forbidden."""
        self.client.force_login(self.user)

        response = self.client.get(reverse("apps.tenancy:tenant_list"))

        self.assertEqual(response.status_code, 403)

    def test_list_shows_registry_tenants(self) -> None:
        """The console lists every client of the platform."""
        grant(self.user, "view_tenant")
        self.client.force_login(self.user)

        response = self.client.get(reverse("apps.tenancy:tenant_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ACME")
        self.assertContains(response, self.acme.slug)

    def test_list_search_matches_slug(self) -> None:
        """The search box filters by slug as well as by name."""
        grant(self.user, "view_tenant")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("apps.tenancy:tenant_list"), {"name_search": "acme"}
        )

        self.assertContains(response, "ACME")


class TenantCreateViewTests(OpsTenantTestCase):
    """Provisioning a client from the console."""

    def setUp(self) -> None:
        """Sign in an operator allowed to provision and to read the list."""
        super().setUp()
        self.user = UserFactory()
        grant(self.user, "view_tenant", "add_tenant")
        self.client.force_login(self.user)

    def provision_payload(self, **overrides: Any) -> dict[str, Any]:
        """Return a valid provisioning payload."""
        payload: dict[str, Any] = {
            "name": "Nueva Planta",
            "slug": "nueva",
            "kind": "final",
            "domain": "",
            "admin_email": "admin@nueva.pe",
            "default_password": "Demo12345!",
            "capabilities": "",
            "primary_color": "#123456",
        }
        payload.update(overrides)
        return payload

    def drop_provisioned_tenant(self, tenant: models.Tenant) -> None:
        """Drop a tenant created by the view and return to the ops schema.

        Dropping a schema is not transactional, so it is a test cleanup; the
        connection is left on ``public`` by the drop, which would break the next
        test's fixtures, so the ops tenant is selected again afterwards.

        Args:
            tenant: The tenant provisioned by the view under test.
        """
        self.drop_tenant(tenant)
        connection.set_tenant(self.tenant)

    def test_create_form_renders(self) -> None:
        """The create page renders for an authorized operator."""
        response = self.client.get(reverse("apps.tenancy:tenant_create"))

        self.assertEqual(response.status_code, 200)

    def test_create_provisions_the_tenant(self) -> None:
        """A valid post creates the schema, domain and administrator."""
        response = self.client.post(
            reverse("apps.tenancy:tenant_create"), self.provision_payload()
        )

        self.assertRedirects(response, reverse("apps.tenancy:tenant_list"))
        tenant = models.Tenant.objects.get(slug="nueva")
        self.addCleanup(self.drop_provisioned_tenant, tenant)
        self.assertEqual(tenant.schema_name, "nueva")
        self.assertEqual(tenant.primary_color, "#123456")
        self.assertTrue(tenant.domains.filter(is_primary=True).exists())

    def test_create_rejects_duplicate_slug(self) -> None:
        """A slug already in the registry is refused before any DDL."""
        make_registry_tenant("acme", "ACME")

        response = self.client.post(
            reverse("apps.tenancy:tenant_create"), self.provision_payload(slug="acme")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("slug", response.context["form"].errors)
        self.assertEqual(models.Tenant.objects.filter(slug="acme").count(), 1)

    def test_create_rejects_the_public_schema_slug(self) -> None:
        """``public`` is the registry schema, not a client."""
        response = self.client.post(
            reverse("apps.tenancy:tenant_create"),
            self.provision_payload(slug="public"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("slug", response.context["form"].errors)

    def test_create_rejects_a_used_domain(self) -> None:
        """A host name already served by another tenant is refused."""
        tenant = make_registry_tenant("acme", "ACME")
        models.Domain.objects.create(domain="taken.test.com", tenant=tenant)

        response = self.client.post(
            reverse("apps.tenancy:tenant_create"),
            self.provision_payload(domain="taken.test.com"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("domain", response.context["form"].errors)

    @mock.patch("apps.tenancy.views.services.provision_tenant")
    def test_create_surfaces_provisioning_errors(self, provision: mock.Mock) -> None:
        """A ``ValueError`` from provisioning becomes a form error."""
        provision.side_effect = ValueError("Domain already belongs to another tenant")

        response = self.client.post(
            reverse("apps.tenancy:tenant_create"), self.provision_payload()
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Domain already belongs", response.context["form"].errors["__all__"][0]
        )


class TenantUpdateViewTests(OpsTenantTestCase):
    """Editing and suspending clients from the console."""

    def setUp(self) -> None:
        """Create a client and sign in an operator allowed to edit."""
        super().setUp()
        self.acme = make_registry_tenant("acme", "ACME", kind="lab")
        self.user = UserFactory()
        grant(self.user, "view_tenant", "change_tenant")
        self.client.force_login(self.user)

    def test_update_form_renders(self) -> None:
        """The update page renders the tenant preloaded."""
        response = self.client.get(
            reverse("apps.tenancy:tenant_update", args=[self.acme.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ACME")

    def test_update_branding_and_capabilities(self) -> None:
        """Branding, capabilities and name are persisted on the registry."""
        response = self.client.post(
            reverse("apps.tenancy:tenant_update", args=[self.acme.pk]),
            {
                "name": "ACME Updated",
                "kind": "lab",
                "is_active": "on",
                "primary_color": "#abcdef",
                "capabilities": '{"labs": true}',
            },
        )

        self.assertRedirects(response, reverse("apps.tenancy:tenant_list"))
        self.acme.refresh_from_db()
        self.assertEqual(self.acme.name, "ACME Updated")
        self.assertEqual(self.acme.primary_color, "#abcdef")
        self.assertEqual(self.acme.capabilities, {"labs": True})

    def test_update_can_deactivate(self) -> None:
        """Omitting the checkbox suspends the client."""
        self.client.post(
            reverse("apps.tenancy:tenant_update", args=[self.acme.pk]),
            {"name": "ACME", "kind": "lab", "capabilities": ""},
        )

        self.acme.refresh_from_db()
        self.assertFalse(self.acme.is_active)

    def test_toggle_active_suspends_and_activates(self) -> None:
        """The suspend/activate action flips the flag in both directions."""
        self.assertTrue(self.acme.is_active)

        self.client.post(
            reverse("apps.tenancy:tenant_toggle_active", args=[self.acme.pk])
        )
        self.acme.refresh_from_db()
        self.assertFalse(self.acme.is_active)

        self.client.post(
            reverse("apps.tenancy:tenant_toggle_active", args=[self.acme.pk])
        )
        self.acme.refresh_from_db()
        self.assertTrue(self.acme.is_active)

    def test_detail_shows_consumption(self) -> None:
        """The detail page measures the tenant's schema."""
        response = self.client.get(
            reverse("apps.tenancy:tenant_detail", args=[self.tenant.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["consumption"]["schema_name"], self.tenant.schema_name
        )


class TenantConsoleIsolationTests(TenantProvisionTestCase):
    """The console is only reachable from the operations tenant."""

    def setUp(self) -> None:
        """Sign in a superuser inside a regular client tenant."""
        super().setUp()
        self.user = UserFactory(is_superuser=True)
        self.client.force_login(self.user)

    def test_list_is_hidden_outside_ops(self) -> None:
        """A regular tenant answers 404 for the registry routes."""
        response = self.client.get(reverse("apps.tenancy:tenant_list"))

        self.assertEqual(response.status_code, 404)

    def test_menu_links_to_organizations_inside_a_client(self) -> None:
        """The aside keeps pointing at organizations outside ``ops``."""
        grant(self.user, "view_organization")
        request = RequestFactory().get("/")
        request.user = self.user
        request.tenant = self.tenant

        html = render_to_string("includes/aside.html", request=request)

        self.assertIn(reverse("apps.organizations:organization_list"), html)
        self.assertNotIn(reverse("apps.tenancy:tenant_list"), html)


class OpsMenuTests(OpsTenantTestCase):
    """The "Clients" menu points at the tenant console inside ``ops``."""

    def test_menu_links_to_tenants(self) -> None:
        """The aside links to the registry and hides the organization tree."""
        user = UserFactory()
        grant(user, "view_tenant", "view_organization")
        request = RequestFactory().get("/")
        request.user = user
        request.tenant = self.tenant

        html = render_to_string("includes/aside.html", request=request)

        self.assertIn(reverse("apps.tenancy:tenant_list"), html)
        self.assertNotIn(reverse("apps.organizations:organization_list"), html)
