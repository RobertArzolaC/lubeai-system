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

from typing import TYPE_CHECKING, Any, ClassVar

from django.apps import apps
from django.conf import settings
from django.contrib.sites.models import Site
from django.db import connection, transaction
from django_tenants.utils import get_public_schema_name, schema_exists, tenant_context

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
    *,
    branding: dict[str, str] | None = None,
    capabilities: dict[str, Any] | None = None,
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
        branding: Optional mapping of branding slot (``primary_color``,
            ``chart_*``) to value. Slots that are absent keep their current
            value, so re-provisioning never erases a brand.
        capabilities: Optional per-tenant capability overrides. ``None`` keeps
            the current value.

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

        resolved_domain = domain or f"{slug}.{settings.PLATFORM_DOMAIN}"
        # Validate the host *before* touching the registry: ``Tenant.save``
        # creates and migrates the schema (DDL, not transactional), so a later
        # failure would leave an orphan schema behind.
        _assert_domain_available(slug=slug, domain=resolved_domain)

        tenant = _upsert_tenant(
            slug=slug,
            name=name,
            kind=kind,
            branding=branding,
            capabilities=capabilities,
        )
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


def _assert_domain_available(*, slug: str, domain: str) -> None:
    """Reject a domain that already belongs to another tenant.

    This runs before any write so a conflict cannot leave a half-provisioned
    tenant (or an orphan schema) behind.

    Args:
        slug: Slug of the tenant being provisioned; a domain already owned by
            the same slug is not a conflict (idempotent re-provisioning).
        domain: Host name the tenant will answer on.

    Raises:
        ValueError: If the host name is registered to a different tenant.
    """
    conflict = (
        models.Domain.objects.filter(domain=domain).exclude(tenant__slug=slug).exists()
    )
    if conflict:
        raise ValueError(f"Domain '{domain}' already belongs to another tenant.")


def _upsert_tenant(
    *,
    slug: str,
    name: str,
    kind: str,
    branding: dict[str, str] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> models.Tenant:
    """Create the tenant row or update its business fields.

    Args:
        slug: Business identifier; also the schema name.
        name: Human-readable tenant name.
        kind: Validated tenant kind.
        branding: Branding slots to write; absent slots are left untouched.
        capabilities: Capability overrides to write; ``None`` leaves the
            current value untouched.

    Returns:
        The saved tenant.
    """
    tenant = models.Tenant.objects.filter(slug=slug).first()
    if tenant is None:
        tenant = models.Tenant(slug=slug, name=name, kind=kind)
    else:
        tenant.name = name
        tenant.kind = kind

    if branding is not None:
        for slot in constants.BRANDING_SLOTS:
            if slot in branding:
                setattr(tenant, slot, branding.get(slot) or "")
    if capabilities is not None:
        tenant.capabilities = capabilities

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


class TenantService:
    """Platform-side operations on the tenant registry.

    The registry lives in the ``public`` schema and belongs to the platform, not
    to any client: these operations are consumed by the operations tenant's
    console (``apps.tenancy.views``) and by billing. Reading the registry works
    from any tenant (``<tenant>, public`` is the search path); writing it is
    restricted by ``TenantMixin.save`` to the public schema, so every method that
    persists a row switches the connection to ``public`` first and restores the
    caller's schema afterwards.
    """

    #: Models counted per tenant for billing. The values reuse each model's
    #: ``_default_manager`` inside the tenant's schema.
    COUNTED_MODELS: ClassVar[dict[str, tuple[str, str]]] = {
        "organizations": ("organizations", "Organization"),
        "users": ("users", "User"),
        "machines": ("equipment", "Machine"),
        "reports": ("reports", "Report"),
    }

    @classmethod
    def consumption(cls, tenant: models.Tenant) -> dict[str, Any]:
        """Return the measurable usage of ``tenant`` for billing.

        ``bytes`` is the on-disk size of every table in the tenant's schema
        (data, indexes and TOAST) as reported by ``pg_total_relation_size``;
        ``rows`` is the sum of the counted rows. The per-model counts are also
        flattened into the result (``organizations``, ``users``, ``machines``,
        ``reports``), so a consumer can bill both storage and activity.

        Args:
            tenant: Tenant whose schema is measured. The ``public`` registry
                schema is rejected by callers, not here; measuring it yields the
                SHARED tables, which are not billable.

        Returns:
            A mapping with ``schema_name``, ``bytes``, ``rows`` and one key per
            entry of :attr:`COUNTED_MODELS`.
        """
        schema_name = tenant.schema_name
        # A registry row may exist before its schema does: the console and the
        # graduation runbook both create the ``Tenant`` row first. Counting the
        # models under ``tenant_context`` would then resolve the unqualified
        # table names against a non-existent schema — an error, or worse, a
        # silent read of the ``public`` tables with the same name. Guarding on
        # the schema keeps the measurement honest: no schema, no usage.
        if not schema_exists(schema_name):
            empty: dict[str, Any] = {
                "schema_name": schema_name,
                "bytes": 0,
                "rows": 0,
            }
            empty.update(dict.fromkeys(cls.COUNTED_MODELS, 0))
            return empty

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(pg_total_relation_size(c.oid)), 0)
                FROM pg_catalog.pg_class AS c
                JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relkind IN ('r', 'p')
                """,
                [schema_name],
            )
            total_bytes = int(cursor.fetchone()[0] or 0)

        counts: dict[str, int] = {}
        with tenant_context(tenant):
            for key, (app_label, model_name) in cls.COUNTED_MODELS.items():
                model = apps.get_model(app_label, model_name)
                counts[key] = model._default_manager.count()

        usage: dict[str, Any] = {
            "schema_name": schema_name,
            "bytes": total_bytes,
            "rows": sum(counts.values()),
        }
        usage.update(counts)
        return usage

    @staticmethod
    def set_active(tenant: models.Tenant, is_active: bool) -> models.Tenant:
        """Suspend or reactivate a tenant by toggling its ``is_active`` flag.

        Writes to the registry require the ``public`` schema, so the connection
        is switched for the write and restored afterwards (the console runs
        inside the operations tenant).

        Args:
            tenant: Tenant to suspend (``is_active=False``) or activate.
            is_active: The desired flag.

        Returns:
            The refreshed tenant.
        """
        previous_tenant = connection.tenant
        try:
            connection.set_schema_to_public()
            tenant.is_active = is_active
            tenant.save(verbosity=0, update_fields=["is_active"])
        finally:
            connection.set_tenant(previous_tenant)
        tenant.refresh_from_db()
        return tenant
