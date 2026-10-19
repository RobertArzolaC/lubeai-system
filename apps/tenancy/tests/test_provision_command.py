"""Tests for tenant provisioning.

Provisioning must leave a client immediately usable: its PostgreSQL schema is
migrated, its host name is registered in ``Domain``, and, inside the schema,
the ``Site``, the root organization, the admin user and the default component
types exist. The public schema is not a client: it has its own tenant row and
``Domain`` but is never provisioned as a business tenant.
"""

from __future__ import annotations

import tempfile
from io import StringIO
from typing import ClassVar

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django_tenants.utils import get_public_schema_name, schema_exists, tenant_context

from apps.equipment import models as equipment_models
from apps.organizations import choices as organization_choices
from apps.organizations import models as organization_models
from apps.tenancy import branding, choices, constants, models, services, signals
from apps.tenancy.management.commands.provision_tenant import Command
from apps.tenancy.tests.base import TenantProvisionTestCase
from apps.users.models import User


class ProvisionTenantTests(TenantProvisionTestCase):
    """Provisioning a tenant leaves it immediately usable."""

    def test_provision_creates_schema_site_and_admin(self) -> None:
        """A new tenant has a schema, a Site and a working admin user."""
        tenant = self.provision()

        self.assertEqual(tenant.schema_name, "acme")
        self.assertTrue(schema_exists("acme"))

        with tenant_context(tenant):
            self.assertEqual(Site.objects.count(), 1)
            self.assertEqual(
                Site.objects.get().domain, tenant.get_primary_domain().domain
            )
            self.assertTrue(User.objects.filter(email="admin@acme.pe").exists())

    def test_provision_creates_the_root_organization(self) -> None:
        """The root organization carries the tenant name and kind."""
        tenant = self.provision()

        with tenant_context(tenant):
            root = organization_models.Organization.objects.get(parent__isnull=True)
            self.assertEqual(root.slug, "acme")
            self.assertEqual(root.name, "ACME")
            self.assertEqual(
                root.kind, organization_choices.OrganizationKind.INTERMEDIARY
            )
            self.assertTrue(root.has_capability("alerts"))

    def test_provision_creates_the_component_type_catalog(self) -> None:
        """Every tenant starts with the standard component types."""
        tenant = self.provision()

        with tenant_context(tenant):
            root = organization_models.Organization.objects.get(parent__isnull=True)
            self.assertEqual(
                equipment_models.ComponentType.objects.filter(
                    organization=root
                ).count(),
                len(constants.DEFAULT_COMPONENT_TYPES),
            )

    def test_provision_registers_the_tenant_domain(self) -> None:
        """The tenant is reachable through ``<slug>.<platform domain>``."""
        tenant = self.provision()

        domain = tenant.get_primary_domain()
        self.assertIsNotNone(domain)
        self.assertEqual(domain.domain, f"acme.{settings.PLATFORM_DOMAIN}")

    @override_settings(TENANT_HOST_SUFFIX="example.test")
    def test_the_derived_host_uses_the_tenant_host_suffix(self) -> None:
        """The derived host follows ``TENANT_HOST_SUFFIX``, not the landing host."""
        tenant = self.provision()

        self.assertEqual(tenant.get_primary_domain().domain, "acme.example.test")

    @override_settings(TENANT_HOST_SUFFIX="example.test")
    def test_an_explicit_domain_wins_over_the_suffix(self) -> None:
        """A client may use a domain unrelated to the platform's own."""
        tenant = self.provision(domain="lubricantes-cliente.com")

        self.assertEqual(
            tenant.get_primary_domain().domain, "lubricantes-cliente.com"
        )

    @override_settings(TENANT_HOST_SUFFIX="")
    def test_provision_requires_an_explicit_domain_without_a_suffix(self) -> None:
        """With no suffix the command refuses to invent a host."""
        with self.assertRaisesMessage(ValueError, "TENANT_HOST_SUFFIX"):
            self.provision(domain=None)

        self.assertFalse(models.Tenant.objects.filter(slug="acme").exists())
        self.assertFalse(schema_exists("acme"))

    def test_provision_grants_the_admin_every_permission(self) -> None:
        """The admin is a superuser, so allauth and the admin work on login."""
        tenant = self.provision()

        with tenant_context(tenant):
            admin = User.objects.get(email="admin@acme.pe")
            self.assertTrue(admin.is_staff)
            self.assertTrue(admin.is_superuser)
            self.assertTrue(admin.has_perm("reports.view_report"))

    def test_provision_is_idempotent(self) -> None:
        """Re-running provisioning does not duplicate any row."""
        tenant = self.provision()
        self.provision()

        self.assertEqual(models.Tenant.objects.filter(slug="acme").count(), 1)
        self.assertEqual(tenant.domains.count(), 1)

        with tenant_context(tenant):
            self.assertEqual(Site.objects.count(), 1)
            self.assertEqual(
                organization_models.Organization.objects.filter(
                    parent__isnull=True
                ).count(),
                1,
            )
            self.assertEqual(
                equipment_models.ComponentType.objects.count(),
                len(constants.DEFAULT_COMPONENT_TYPES),
            )
            self.assertEqual(User.objects.filter(email="admin@acme.pe").count(), 1)

    def test_reprovision_does_not_promote_a_normal_user(self) -> None:
        """I4: re-running provisioning never escalates a pre-existing account."""
        tenant = self.provision()
        with tenant_context(tenant):
            # Stand in for a pre-existing, non-privileged account that happens to
            # use the administrator email.
            admin = User.objects.get(email="admin@acme.pe")
            admin.is_superuser = False
            admin.is_staff = False
            admin.save(update_fields=["is_superuser", "is_staff"])
            self.assertFalse(admin.is_superuser)

        self.provision()

        with tenant_context(tenant):
            normal = User.objects.get(email="admin@acme.pe")
            self.assertFalse(normal.is_superuser)
            self.assertFalse(normal.is_staff)

    def test_reprovision_promotes_with_an_explicit_opt_in(self) -> None:
        """I4: promoting a pre-existing account requires ``promote=True``."""
        tenant = self.provision()
        with tenant_context(tenant):
            admin = User.objects.get(email="admin@acme.pe")
            admin.is_superuser = False
            admin.is_staff = False
            admin.save(update_fields=["is_superuser", "is_staff"])

        self.provision(promote=True)

        with tenant_context(tenant):
            normal = User.objects.get(email="admin@acme.pe")
            self.assertTrue(normal.is_superuser)
            self.assertTrue(normal.is_staff)

    def test_domain_conflict_leaves_no_tenant_or_schema(self) -> None:
        """A domain owned by another tenant fails before any write."""
        self.provision()

        with self.assertRaisesMessage(ValueError, "already belongs to another tenant"):
            services.provision_tenant(
                slug="beta",
                name="Beta",
                kind=choices.TenantKind.INTERMEDIARY.value,
                admin_email="admin@beta.pe",
                default_password="Demo12345!",
                domain=f"acme.{settings.PLATFORM_DOMAIN}",
            )

        self.assertFalse(models.Tenant.objects.filter(slug="beta").exists())
        self.assertFalse(schema_exists("beta"))

    def test_provision_never_creates_a_schema_for_public(self) -> None:
        """The public schema is the registry, not a provisioned client."""
        with self.assertRaises(ValueError):
            services.provision_tenant(
                slug="public",
                name="Public",
                kind=choices.TenantKind.PLATFORM.value,
                admin_email="admin@example.com",
                default_password="Demo12345!",
            )

        public = models.Tenant.objects.get(schema_name=get_public_schema_name())
        self.assertEqual(public.kind, choices.TenantKind.PLATFORM)
        self.assertFalse(
            models.Domain.objects.filter(
                domain=f"public.{settings.PLATFORM_DOMAIN}"
            ).exists()
        )

    def test_provision_command_runs_the_service(self) -> None:
        """``provision_tenant`` is callable as a management command."""
        call_command(
            "provision_tenant",
            slug="acme",
            name="ACME",
            kind=choices.TenantKind.INTERMEDIARY.value,
            admin_email="admin@acme.pe",
            default_password="Demo12345!",
            verbosity=0,
        )
        tenant = models.Tenant.objects.get(slug="acme")
        self.addCleanup(self.drop_tenant, tenant)

        self.assertTrue(schema_exists("acme"))
        with tenant_context(tenant):
            self.assertTrue(User.objects.filter(email="admin@acme.pe").exists())

    def test_provision_command_generates_a_password_when_omitted(self) -> None:
        """There is no repository default: a random password is printed once."""
        output = self._run_command()

        tenant = models.Tenant.objects.get(slug="acme")
        self.addCleanup(self.drop_tenant, tenant)

        password = self._printed_password(output)
        self.assertNotEqual(password, constants.DEMO_PASSWORD)
        with tenant_context(tenant):
            admin = User.objects.get(email="admin@acme.pe")
            self.assertTrue(admin.check_password(password))

    def test_provision_command_rejects_a_weak_password(self) -> None:
        """The CLI validates the password exactly like the tenant console."""
        with self.assertRaises(CommandError):
            call_command(
                "provision_tenant",
                slug="acme",
                name="ACME",
                kind=choices.TenantKind.INTERMEDIARY.value,
                admin_email="admin@acme.pe",
                default_password="123",
                verbosity=0,
                no_color=True,
            )

        self.assertFalse(models.Tenant.objects.filter(slug="acme").exists())

    def test_provision_command_keeps_an_existing_password(self) -> None:
        """An existing administrator keeps it, so nothing is echoed."""
        tenant = self.provision()

        output = self._run_command(default_password="OtherPassword123!")

        self.assertNotIn("OtherPassword123!", output)
        self.assertIn("password was not changed", output)
        with tenant_context(tenant):
            admin = User.objects.get(email="admin@acme.pe")
            self.assertTrue(admin.check_password("Demo12345!"))
            self.assertFalse(admin.check_password("OtherPassword123!"))

    def test_provision_command_reports_a_service_error(self) -> None:
        """A service ``ValueError`` reaches the operator as a ``CommandError``."""
        with self.assertRaises(CommandError):
            self._run_command(
                slug="public",
                name="Public",
                kind=choices.TenantKind.PLATFORM.value,
                admin_email="admin@public.test",
            )

    def test_admin_exists_ignores_an_unregistered_schema(self) -> None:
        """A schema an operator created by hand is not a provisioned tenant."""
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS outer_space")

        self.assertTrue(schema_exists("outer_space"))
        self.assertFalse(
            Command._admin_exists(slug="outer_space", email="admin@outer.test")
        )

    def test_admin_exists_ignores_the_registry_schema(self) -> None:
        """The public schema is not a client, so it is never probed."""
        self.assertTrue(schema_exists(get_public_schema_name()))
        self.assertFalse(
            Command._admin_exists(
                slug=get_public_schema_name(), email="admin@public.test"
            )
        )

    def _run_command(self, **overrides: object) -> str:
        """Run the provisioning command and return its stdout.

        Args:
            **overrides: Options forwarded to ``call_command``.

        Returns:
            Everything the command wrote to stdout.
        """
        options: dict[str, object] = {
            "slug": "acme",
            "name": "ACME",
            "kind": choices.TenantKind.INTERMEDIARY.value,
            "admin_email": "admin@acme.pe",
            "verbosity": 0,
            "no_color": True,
        }
        options.update(overrides)
        output = StringIO()
        call_command("provision_tenant", stdout=output, **options)
        return output.getvalue()

    @staticmethod
    def _printed_password(output: str) -> str:
        """Return the administrator password echoed by the command.

        Args:
            output: The command's stdout.

        Returns:
            The password printed on the ``- Admin password:`` line.

        Raises:
            AssertionError: If the command did not print a password.
        """
        marker = "- Admin password:"
        for line in output.splitlines():
            if line.startswith(marker):
                return line[len(marker) :].strip()
        raise AssertionError(f"The command printed no administrator password: {output}")


class RequestStartedSignalTests(TenantProvisionTestCase):
    """easy-audit's request log must run on the request's schema."""

    ENVIRON: ClassVar[dict[str, str]] = {
        "PATH_INFO": "/",
        "REQUEST_METHOD": "GET",
        "QUERY_STRING": "",
    }

    def hit(self, host: str) -> None:
        """Send ``request_started`` for ``host`` through the resolver.

        Args:
            host: Host name of the request.
        """
        signals.request_started_handler(
            None, environ={**self.ENVIRON, "HTTP_HOST": host}
        )

    def test_selects_the_tenant_before_easy_audit_logs(self) -> None:
        """A tenant host leaves the connection on that tenant's schema."""
        self.provision()

        self.hit("acme.localhost")

        self.assertEqual(connection.schema_name, "acme")

    def test_public_host_stays_on_public(self) -> None:
        """The public schema has no audit table, so requests there are skipped."""
        connection.set_schema_to_public()

        self.hit(settings.PLATFORM_DOMAIN)

        self.assertEqual(connection.schema_name, get_public_schema_name())

    def test_unknown_host_is_not_resolved(self) -> None:
        """A host with no Domain is left for the tenant middleware to 404."""
        connection.set_schema_to_public()

        self.hit("unknown.test.com")

        self.assertEqual(connection.schema_name, get_public_schema_name())


class PublicTenantTests(TestCase):
    """The public schema has its own tenant row, reachable by host."""

    def test_public_tenant_and_domain_exist(self) -> None:
        """Without them the public landing page would be unreachable."""
        tenant = models.Tenant.objects.get(schema_name=get_public_schema_name())

        self.assertEqual(tenant.kind, choices.TenantKind.PLATFORM)
        self.assertEqual(tenant.slug, get_public_schema_name())
        self.assertEqual(tenant.get_primary_domain().domain, settings.PLATFORM_DOMAIN)

    @override_settings(ALLOWED_HOSTS=["*"])
    def test_public_landing_is_reachable_through_the_public_domain(self) -> None:
        """A request to the public host resolves the landing urlconf."""
        domain = models.Domain.objects.get(tenant__schema_name="public")

        response = self.client.get("/", HTTP_HOST=domain.domain)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "public/landing.html")


class KnownBrandProvisionTests(TenantProvisionTestCase):
    """A client with a known brand is provisioned already branded."""

    def test_provision_applies_the_known_brand_of_its_client(self) -> None:
        """Creating the MARCO tenant gives MARCO's brand, not the default."""
        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            tenant = self.provision(
                slug="marco",
                name="MARCO Peruana",
                kind=choices.TenantKind.LAB.value,
                admin_email="admin@marco.pe",
            )

            expected = branding.KNOWN_BRANDS["marco"]
            self.assertEqual(tenant.primary_color, expected["primary_color"])
            self.assertEqual(tenant.chart_info, expected["chart_info"])
            self.assertTrue(tenant.logo)

            with tenant_context(tenant):
                root = organization_models.Organization.objects.get(
                    parent__isnull=True
                )
                self.assertEqual(root.primary_color, expected["primary_color"])
                self.assertTrue(root.logo)

    def test_an_explicit_branding_argument_wins_over_the_known_brand(self) -> None:
        """The caller can override a client's brand slots."""
        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            tenant = self.provision(
                slug="marco",
                kind=choices.TenantKind.LAB.value,
                branding={"primary_color": "#123456"},
            )

            self.assertEqual(tenant.primary_color, "#123456")

    def test_a_client_without_a_known_brand_keeps_the_defaults(self) -> None:
        """An unknown slug is not branded by guessing."""
        tenant = self.provision()

        self.assertEqual(tenant.primary_color, "")
        self.assertFalse(tenant.logo)
