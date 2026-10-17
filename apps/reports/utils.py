from apps.reports import choices

# Default color mapping for parameters (used when no organization palette is provided)
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

# Maps parameter constants to palette color keys for organization-aware resolution
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


def get_parameter_color(parameter: str, organization: object | None = None) -> str:
    """
    Get the color associated with a specific parameter.

    When an ``organization`` is provided, colors are resolved from the
    organization's branded palette via
    :class:`apps.organizations.services.ColorPaletteService`. Otherwise,
    hardcoded defaults are used.

    Args:
        parameter: The parameter key (e.g., 'iron_fe', 'silicon_si').
        organization: Optional Organization instance for branded colors.

    Returns:
        Hex color code for the parameter, or default gray if not found.
    """
    if organization is not None:
        from apps.organizations.services import ColorPaletteService

        palette_key = _PARAMETER_PALETTE_MAP.get(parameter)
        if palette_key:
            palette = ColorPaletteService.get_palette(organization)
            return palette.get(palette_key, DEFAULT_PARAMETER_COLOR)

    return _DEFAULT_PARAMETER_COLORS.get(parameter, DEFAULT_PARAMETER_COLOR)
