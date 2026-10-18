"""Tests for the shared tenancy registry."""

from typing import Any

from django.conf import settings
from django.db import connection
from django.test import TestCase

from apps.tenancy import choices, models


def create_tenant_without_schema(**fields: Any) -> models.Tenant:
    """Create a tenant row without creating its PostgreSQL schema.

    ``auto_create_schema`` is a documented flag of
    :class:`~django_tenants.models.TenantMixin`; disabling it keeps the tests
    that only exercise the registry's relationships fast.
    """
    tenant = models.Tenant(**fields)
    tenant.auto_create_schema = False
    tenant.save()
    return tenant


class TenantModelTests(TestCase):
    """``Tenant`` is the hard isolation boundary of the platform."""

    def test_tenant_creation_creates_schema(self) -> None:
        """Creating a tenant creates its PostgreSQL schema."""
        tenant = models.Tenant.objects.create(name="ACME", slug="acme")
        self.assertEqual(tenant.schema_name, "acme")
        self.assertTrue(tenant.is_active)

    def test_tenant_schema_is_usable_and_isolated(self) -> None:
        """Tenant schemas hold TENANT apps only; SHARED apps stay in public."""
        tenant = models.Tenant.objects.create(name="ACME", slug="acme")
        schema = tenant.schema_name

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass(%s), to_regclass(%s),"
                " to_regclass(%s), to_regclass(%s)",
                [
                    f"{schema}.auth_group",
                    f"{schema}.tenancy_tenant",
                    "public.tenancy_tenant",
                    "public.auth_group",
                ],
            )
            (
                tenant_table,
                shared_table_in_tenant,
                shared_table,
                tenant_table_in_public,
            ) = cursor.fetchone()

        self.assertIsNotNone(tenant_table, "TENANT apps must be migrated per schema")
        self.assertIsNotNone(shared_table, "SHARED apps must live in public")
        self.assertIsNone(
            shared_table_in_tenant, "SHARED apps must not be duplicated per tenant"
        )
        self.assertIsNone(
            tenant_table_in_public, "TENANT apps must not be migrated into public"
        )

    def test_tenant_defaults(self) -> None:
        """New tenants are active clients of the final-client kind."""
        tenant = create_tenant_without_schema(name="ACME", slug="acme")

        self.assertEqual(tenant.kind, choices.TenantKind.FINAL)
        self.assertEqual(tenant.capabilities, {})
        self.assertEqual(str(tenant), "ACME")


class DomainModelTests(TestCase):
    """A tenant is reachable through the host names stored in ``Domain``."""

    def test_domain_is_attached_to_its_tenant(self) -> None:
        """Saving a domain links it to the tenant and makes it primary."""
        tenant = create_tenant_without_schema(name="ACME", slug="acme")

        domain = models.Domain.objects.create(
            domain="acme.midominio.com", tenant=tenant
        )

        self.assertTrue(domain.is_primary)
        self.assertEqual(tenant.domains.count(), 1)
        self.assertEqual(tenant.get_primary_domain(), domain)


class TenancySettingsTests(TestCase):
    """The registry must be wired as a SHARED app to resolve tenants."""

    def test_registry_is_shared(self) -> None:
        """``apps.tenancy`` lives in public and is the tenant model source."""
        self.assertIn("apps.tenancy", settings.SHARED_APPS)
        self.assertNotIn("apps.tenancy", settings.TENANT_APPS)
        self.assertEqual(settings.TENANT_MODEL, "tenancy.Tenant")
        self.assertEqual(settings.TENANT_DOMAIN_MODEL, "tenancy.Domain")
        self.assertIn(
            "django_tenants.routers.TenantSyncRouter", settings.DATABASE_ROUTERS
        )


class SharedBoundaryTests(TestCase):
    """No SHARED model may reference a TENANT model."""

    def test_registry_models_only_reference_shared_models(self) -> None:
        """A SHARED -> TENANT reference would dangle in the public schema."""
        shared_apps = set(settings.SHARED_APPS)

        for model in (models.Tenant, models.Domain):
            for field in model._meta.get_fields():
                related = getattr(field, "related_model", None)
                if related is None:
                    continue
                self.assertIn(
                    related._meta.app_config.name,
                    shared_apps,
                    msg=(
                        f"{model._meta.label}.{field.name} references "
                        f"{related._meta.label}, which is not a SHARED app"
                    ),
                )
