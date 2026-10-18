"""Provisioning services for the shared tenancy registry.

:func:`provision_tenant` turns a row of the registry into a client that can be
used immediately: it creates the PostgreSQL schema (and migrates it), registers
the host name, and seeds the minimum data a tenant needs inside its own schema
(``Site``, root organization, admin user and the standard component types).

The function is idempotent: re-running it updates the registry row and restores
any missing seed data without duplicating rows. It never creates a schema for
the ``public`` registry schema, which is not a business tenant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name, tenant_context

from apps.tenancy import choices, constants, models

if TYPE_CHECKING:
    from apps.organizations.models import Organization
    from apps.users.models import User


def provision_tenant(
    slug: str,
    name: str,
    kind: str,
    admin_email: str,
    default_password: str,
    domain: str | None = None,
) -> models.Tenant:
    """Create (or complete) a tenant and leave it ready to be served.

    A new tenant gets its schema created and migrated by ``Tenant.save``
    (``auto_create_schema``). An existing tenant keeps its schema; migrations
    for already existing schemas are the deploy step's responsibility
    (``migrate_schemas``). In both cases the domain, ``Site``, root
    organization, admin user and default component types are ensured.

    Args:
        slug: Business identifier; also the PostgreSQL schema name.
        name: Human-readable tenant name.
        kind: One of :class:`apps.tenancy.choices.TenantKind`'s values.
        admin_email: Email of the tenant administrator.
        default_password: Password set on a newly created administrator only;
            an existing administrator keeps its password.
        domain: Host name served by the tenant. Defaults to
            ``<slug>.<PLATFORM_DOMAIN>``.

    Returns:
        The provisioned tenant, refreshed after the writes.

    Raises:
        ValueError: If ``slug`` is the public schema or ``kind`` is not a valid
            tenant kind, or if ``domain`` already belongs to another tenant.
    """
    public_schema = get_public_schema_name()
    if slug == public_schema:
        raise ValueError(
            f"'{public_schema}' is the registry schema, not a provisionable tenant."
        )
    if kind not in set(choices.TenantKind.values):
        raise ValueError(f"Unknown tenant kind: {kind!r}.")

    previous_tenant = connection.tenant
    try:
        connection.set_schema_to_public()

        tenant = _upsert_tenant(slug=slug, name=name, kind=kind)
        resolved_domain = domain or f"{slug}.{settings.PLATFORM_DOMAIN}"
        _ensure_domain(tenant=tenant, domain=resolved_domain)

        with tenant_context(tenant), transaction.atomic():
            _ensure_site(tenant=tenant, domain=resolved_domain)
            root = _ensure_root_organization(
                tenant=tenant, slug=slug, name=name, kind=kind
            )
            _ensure_admin(
                root=root,
                admin_email=admin_email,
                default_password=default_password,
            )
            _ensure_component_types(root=root)
    finally:
        connection.set_tenant(previous_tenant)

    tenant.refresh_from_db()
    return tenant


def _upsert_tenant(*, slug: str, name: str, kind: str) -> models.Tenant:
    """Create the tenant row or update its business fields.

    Args:
        slug: Business identifier; also the schema name.
        name: Human-readable tenant name.
        kind: Validated tenant kind.

    Returns:
        The saved tenant.
    """
    tenant = models.Tenant.objects.filter(slug=slug).first()
    if tenant is None:
        tenant = models.Tenant(slug=slug, name=name, kind=kind)
    else:
        tenant.name = name
        tenant.kind = kind
    tenant.save(verbosity=0)
    return tenant


def _ensure_domain(*, tenant: models.Tenant, domain: str) -> models.Domain:
    """Register ``domain`` as the tenant's primary host name.

    Args:
        tenant: Tenant that will answer on the host.
        domain: Host name to register.

    Returns:
        The tenant's domain row.

    Raises:
        ValueError: If the host name is already registered to another tenant.
    """
    domain_row, created = models.Domain.objects.get_or_create(
        domain=domain, defaults={"tenant": tenant}
    )
    if not created and domain_row.tenant_id != tenant.pk:
        raise ValueError(f"Domain '{domain}' already belongs to another tenant.")
    if not domain_row.is_primary:
        domain_row.is_primary = True
        domain_row.save(update_fields=["is_primary"])
    return domain_row


def _ensure_site(*, tenant: models.Tenant, domain: str) -> Site:
    """Point the schema's ``Site`` at the tenant's own domain.

    ``django.contrib.sites`` is a TENANT app: allauth resolves the current site
    with ``SITE_ID`` and fails on the first login when the row is missing.

    Args:
        tenant: Tenant being provisioned.
        domain: Host name the tenant answers on.

    Returns:
        The schema's ``Site`` row.
    """
    site, _ = Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": domain, "name": tenant.name},
    )
    return site


def _ensure_root_organization(
    *, tenant: models.Tenant, slug: str, name: str, kind: str
) -> Organization:
    """Return the schema's root organization, creating it if it is missing.

    The root is the tenant's own node in the organization tree. Only one root
    may exist, so an existing one is updated instead of duplicated.

    Args:
        tenant: Tenant being provisioned.
        slug: Tenant slug, used as the root's slug on creation.
        name: Tenant name.
        kind: Tenant kind; organization kinds share the same values.

    Returns:
        The root organization.
    """
    from apps.organizations import models as organization_models

    branding = {
        slot: value
        for slot in constants.BRANDING_SLOTS
        if (value := getattr(tenant, slot, ""))
    }
    root = organization_models.Organization.objects.filter(parent__isnull=True).first()
    if root is None:
        return organization_models.Organization.objects.create(
            slug=slug, name=name, kind=kind, **branding
        )

    root.name = name
    root.kind = kind
    for slot, value in branding.items():
        setattr(root, slot, value)
    root.save()
    return root


def _ensure_admin(
    *,
    root: Organization,
    admin_email: str,
    default_password: str,
) -> User:
    """Create (or complete) the tenant administrator.

    A newly created administrator is a superuser, so it holds every permission
    the tenant schema knows about. An existing one keeps its password and only
    gets its organization and flags restored.

    Args:
        root: Root organization the administrator belongs to.
        admin_email: Administrator email.
        default_password: Password for a newly created administrator.

    Returns:
        The administrator user.
    """
    from allauth.account.models import EmailAddress

    from apps.users.models import User

    admin, created = User.objects.get_or_create(
        email=admin_email,
        defaults={
            "first_name": "Administrator",
            "last_name": root.name,
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
            "organization": root,
        },
    )
    if created:
        admin.set_password(default_password)
    admin.organization = root
    admin.is_active = True
    admin.is_staff = True
    admin.is_superuser = True
    admin.save()

    EmailAddress.objects.update_or_create(
        user=admin,
        email=admin.email,
        defaults={"primary": True, "verified": True},
    )
    return admin


def _ensure_component_types(*, root: Organization) -> None:
    """Create the standard component types owned by the root organization.

    Args:
        root: Root organization that owns the catalog.
    """
    from apps.equipment import models as equipment_models

    for name, description in constants.DEFAULT_COMPONENT_TYPES:
        equipment_models.ComponentType.objects.get_or_create(
            organization=root,
            name=name,
            defaults={"description": description},
        )
