"""Real client brands (palette and logo) applied to their demo tenants.

Only the clients this platform actually operates have a known brand. The values
are not invented: each palette is extracted from the client's own public site
and the logo is the client's official asset (the exact provenance is recorded in
``.superpowers/sdd/2026-10-18-multi-tenant-marco-esquemas/task-8-report.md``).
A tenant whose slug is not listed keeps the platform defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

#: Directory holding the packaged logo assets.
ASSETS_DIR: Final[Path] = Path(__file__).resolve().parent / "assets"

#: Branding slots per tenant slug (the same slots as
#: ``apps.organizations.constants.BRANDING_SLOTS``). They are duplicated instead
#: of imported because that app is a TENANT app and this module is SHARED.
KNOWN_BRANDS: Final[dict[str, dict[str, str]]] = {
    "marco": {
        "primary_color": "#002440",
        "chart_primary": "#002440",
        "chart_success": "#398f14",
        "chart_warning": "#ffb500",
        "chart_danger": "#b81c23",
        "chart_info": "#08c8f7",
        "chart_dark": "#002343",
    },
}

#: Logo asset file name per tenant slug, inside :data:`ASSETS_DIR`.
LOGO_ASSETS: Final[dict[str, str]] = {
    "marco": "marco-logo.png",
}

#: Storage folder the logo assets are copied into (matches ``Tenant.logo``).
LOGO_UPLOAD_DIR: Final[str] = "tenants/logos"


def branding_for(slug: str) -> dict[str, str] | None:
    """Return the known branding of a tenant.

    Args:
        slug: Tenant slug.

    Returns:
        A copy of the branding slots for the slug, or ``None`` when the tenant
        has no known brand.
    """
    brand = KNOWN_BRANDS.get(slug)
    return dict(brand) if brand else None


def install_logo(slug: str) -> str | None:
    """Copy the tenant's official logo into the default media storage.

    The asset ships with the app and is written to storage only when it is not
    there yet; the stored name is returned so it can be assigned to more than
    one ``ImageField`` (the tenant and its root organization show the same file
    without storing it twice).

    Args:
        slug: Tenant slug.

    Returns:
        The storage name of the logo, or ``None`` when the tenant has no logo
        asset.
    """
    file_name = LOGO_ASSETS.get(slug)
    if file_name is None:
        return None

    from django.core.files import File
    from django.core.files.storage import default_storage

    name = f"{LOGO_UPLOAD_DIR}/{file_name}"
    if not default_storage.exists(name):
        with (ASSETS_DIR / file_name).open("rb") as handle:
            default_storage.save(name, File(handle))
    return name
