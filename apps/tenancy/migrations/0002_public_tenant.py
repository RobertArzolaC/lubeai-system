"""Create the tenant row and domain of the ``public`` schema.

``public`` is not a business tenant: it holds the registry (this app) and the
shared reference data. It still needs a ``Tenant`` row and a ``Domain`` so that
``TenantMainMiddleware`` can resolve the platform's own host and serve
``PUBLIC_SCHEMA_URLCONF`` (the landing page). Without them a request to
``PLATFORM_DOMAIN`` would answer 404.

The row is created through the historical model, whose ``save`` does not create
or migrate a schema: the public schema already exists and must never be
provisioned as a client.
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import migrations

PUBLIC_SCHEMA = "public"
PUBLIC_SLUG = "public"
PLATFORM_NAME = "Platform"


def create_public_tenant(apps, schema_editor) -> None:
    """Create the public tenant row and its domain if they are missing.

    Args:
        apps: Historical app registry provided by the migration.
        schema_editor: Database schema editor (unused).
    """
    tenant_model = apps.get_model("tenancy", "Tenant")
    domain_model = apps.get_model("tenancy", "Domain")
    domain = getattr(settings, "PLATFORM_DOMAIN", "localhost")

    tenant = tenant_model.objects.filter(schema_name=PUBLIC_SCHEMA).first()
    if tenant is None:
        tenant = tenant_model(
            schema_name=PUBLIC_SCHEMA,
            name=PLATFORM_NAME,
            slug=PUBLIC_SLUG,
            kind="platform",
            is_active=True,
        )
        # ``bulk_create`` bypasses ``save`` and its signals: the historical
        # model must not create a schema, and easyaudit (a TENANT app) must not
        # try to write a CRUD event into the public schema.
        tenant_model.objects.bulk_create([tenant])

    if not domain_model.objects.filter(domain=domain).exists():
        domain_model.objects.bulk_create([domain_model(domain=domain, tenant=tenant)])


def remove_public_tenant(apps, schema_editor) -> None:
    """Remove the public tenant row and its domain (reverse migration).

    The conditional delete runs as raw SQL so the historical model does not
    emit signals for a row the registry no longer owns.

    Args:
        apps: Historical app registry provided by the migration.
        schema_editor: Database schema editor, used for the delete.
    """
    schema_editor.execute(
        'DELETE FROM "tenancy_tenant" WHERE schema_name = %s AND slug = %s',
        [PUBLIC_SCHEMA, PUBLIC_SLUG],
    )


class Migration(migrations.Migration):
    """Create the public schema's tenant registry entry."""

    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("tenancy", "0001_initial"),
    ]

    operations: ClassVar[list[migrations.RunPython]] = [
        migrations.RunPython(create_public_tenant, remove_public_tenant),
    ]
