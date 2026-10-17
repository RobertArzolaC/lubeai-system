"""Services for the organizations app."""

from __future__ import annotations

from apps.organizations import constants


class ColorPaletteService:
    """Resolve the chart color palette for an organization.

    The palette keys match the branding slots (``chart_primary``,
    ``chart_success``, ``chart_warning``, ``chart_danger``, ``chart_info``,
    ``chart_dark``) so callers can resolve a color by slot name.
    """

    @staticmethod
    def get_palette(organization: object | None = None) -> dict:
        """Return the palette for ``organization`` (defaults when ``None``).

        Args:
            organization: An ``Organization`` instance or ``None``.

        Returns:
            Mapping of branding slot names to hex colors.
        """
        if organization is None:
            return dict(constants.DEFAULT_BRANDING)
        return organization.get_branding()
