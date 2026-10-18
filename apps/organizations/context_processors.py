"""Context processors for the organizations app."""

from __future__ import annotations

from typing import Any

from constance import config

from apps.organizations import constants


def _tenant_branding(tenant: Any) -> dict[str, Any]:
    """Return the branding declared on the tenant itself.

    The tenant is the platform client and owns the brand; slots it leaves empty
    fall back to :data:`apps.organizations.constants.DEFAULT_BRANDING`, exactly
    as :meth:`apps.organizations.models.Organization.get_branding` does one level
    down.

    Args:
        tenant: The request tenant (``apps.tenancy.models.Tenant``).

    Returns:
        The resolved branding palette plus its ``logo``.
    """
    branding: dict[str, Any] = dict(constants.DEFAULT_BRANDING)
    for slot in constants.BRANDING_SLOTS:
        value = getattr(tenant, slot, "")
        if value:
            branding[slot] = value
    branding["logo"] = tenant.logo or None
    return branding


def _tenant_capabilities(tenant: Any) -> dict[str, Any]:
    """Return the capabilities of a tenant, overridden by its own JSON field.

    Args:
        tenant: The request tenant (``apps.tenancy.models.Tenant``). Its ``kind``
            reuses the organization kind values, so the kind defaults apply
            unchanged.

    Returns:
        The capability flags that are on for this tenant.
    """
    capabilities: dict[str, Any] = dict(
        constants.DEFAULT_CAPABILITIES.get(tenant.kind, {})
    )
    capabilities.update(tenant.capabilities or {})
    return capabilities


def branding(request: Any) -> dict[str, Any]:
    """Expose the resolved branding and current organization to templates.

    Args:
        request: The current HTTP request. ``request.tenant`` is set by
            ``django_tenants.middleware.main.TenantMainMiddleware`` and
            ``request.organization`` by a view that resolves a node of the
            tenant's organization tree. Both may be missing (the ``public``
            schema, background jobs) and the processor degrades to the platform
            defaults.

    Returns:
        Context with ``branding``, ``current_organization``, ``current_tenant``,
        the resolved ``capabilities`` and the derived ``show_labs`` /
        ``show_fleet`` toggles (global flag OR per-tenant capability).
    """
    tenant = getattr(request, "tenant", None)
    organization = getattr(request, "organization", None)

    if organization is not None:
        branding_data = organization.get_branding()
        capabilities = organization.resolved_capabilities()
    elif tenant is not None:
        branding_data = _tenant_branding(tenant)
        capabilities = _tenant_capabilities(tenant)
    else:
        branding_data = dict(constants.DEFAULT_BRANDING)
        branding_data["logo"] = None
        capabilities = {}

    return {
        "branding": branding_data,
        "current_organization": organization,
        "current_tenant": tenant,
        "capabilities": capabilities,
        "show_labs": bool(config.ENABLE_LABS or capabilities.get("labs")),
        "show_fleet": bool(config.ENABLE_FLEET or capabilities.get("fleet")),
    }
