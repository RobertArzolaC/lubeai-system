"""Context processors for the organizations app."""

from __future__ import annotations

from constance import config

from apps.organizations import constants


def branding(request) -> dict:
    """Expose the resolved branding and current organization to templates.

    Args:
        request: The current HTTP request (expects ``organization``/``tenant``
            set by ``TenantMiddleware``, but degrades gracefully when missing).

    Returns:
        Context with ``branding``, ``current_organization``, ``current_tenant``,
        the resolved ``capabilities`` and the derived ``show_labs`` /
        ``show_fleet`` toggles (global flag OR per-tenant capability).
    """
    organization = getattr(request, "organization", None)

    if organization is not None:
        branding_data = organization.get_branding()
        capabilities = organization.resolved_capabilities()
    else:
        branding_data = dict(constants.DEFAULT_BRANDING)
        branding_data["logo"] = None
        capabilities = {}

    return {
        "branding": branding_data,
        "current_organization": organization,
        "current_tenant": getattr(request, "tenant", None),
        "capabilities": capabilities,
        "show_labs": bool(config.ENABLE_LABS or capabilities.get("labs")),
        "show_fleet": bool(config.ENABLE_FLEET or capabilities.get("fleet")),
    }
