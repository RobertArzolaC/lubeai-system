from typing import Optional

from apps.reports import choices

# Default color mapping for parameters (used when no tenant palette is provided)
_DEFAULT_PARAMETER_COLORS: dict[str, str] = {
    choices.Parameter.IRON_FE: "#F1416C",  # Red
    choices.Parameter.COPPER_CU: "#FFC700",  # Yellow
    choices.Parameter.ALUMINUM_AL: "#009EF7",  # Blue
    choices.Parameter.SILICON_SI: "#181C32",  # Dark gray
    choices.Parameter.SODIUM_NA: "#009EF7",  # Blue
    choices.Parameter.POTASSIUM_K: "#50CD89",  # Green
    choices.Parameter.VISCOSITY_100C: "#FFC700",  # Yellow
    choices.Parameter.ZINC_ZN: "#7239EA",  # Purple
    choices.Parameter.PHOSPHORUS_P: "#F1416C",  # Red
    choices.Parameter.MAGNESIUM_MG: "#50CD89",  # Green
    choices.Parameter.CALCIUM_CA: "#FFC700",  # Yellow
}

# Maps parameter constants to palette color keys for tenant-aware resolution
_PARAMETER_PALETTE_MAP: dict[str, str] = {
    choices.Parameter.IRON_FE: "chart_danger",
    choices.Parameter.COPPER_CU: "chart_warning",
    choices.Parameter.ALUMINUM_AL: "chart_primary",
    choices.Parameter.SILICON_SI: "chart_dark",
    choices.Parameter.SODIUM_NA: "chart_primary",
    choices.Parameter.POTASSIUM_K: "chart_success",
    choices.Parameter.VISCOSITY_100C: "chart_warning",
    choices.Parameter.ZINC_ZN: "chart_info",
    choices.Parameter.PHOSPHORUS_P: "chart_danger",
    choices.Parameter.MAGNESIUM_MG: "chart_success",
    choices.Parameter.CALCIUM_CA: "chart_warning",
}

DEFAULT_PARAMETER_COLOR = "#6C757D"


def get_parameter_color(parameter: str, tenant: Optional[object] = None) -> str:
    """
    Get the color associated with a specific parameter.

    When a ``tenant`` is provided, colors are resolved from the tenant's
    palette via :class:`ColorPaletteService`. Otherwise, hardcoded defaults
    are used.

    Args:
        parameter: The parameter key (e.g., 'iron_fe', 'silicon_si').
        tenant: Optional Client instance for tenant-aware color resolution.

    Returns:
        Hex color code for the parameter, or default gray if not found.
    """
    if tenant is not None:
        from apps.core.services.color_palette_service import ColorPaletteService

        palette_key = _PARAMETER_PALETTE_MAP.get(parameter)
        if palette_key:
            palette = ColorPaletteService.get_palette(tenant)
            return palette.get(palette_key, DEFAULT_PARAMETER_COLOR)

    return _DEFAULT_PARAMETER_COLORS.get(parameter, DEFAULT_PARAMETER_COLOR)
