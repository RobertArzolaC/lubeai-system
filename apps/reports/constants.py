"""Constants and configuration for the reports app.

Includes the export limits and the component analysis configuration used by
:class:`apps.reports.services.component_analysis.ComponentAnalysisService`.

User-facing labels use ``gettext_lazy`` so they are translated at render time
(``JsonResponse`` resolves ``Promise`` objects with the active language).
"""

from typing import Any, Final

from django.utils.translation import gettext_lazy as _

MAX_EXPORT_RECORDS = 10000

# ---------------------------------------------------------------------------
# Component analysis configuration
# ---------------------------------------------------------------------------

# Human readable labels for the ``LabAnalysis`` parameter keys.
PARAMETER_LABELS: Final[dict[str, Any]] = {
    "iron_fe": _("Iron (Fe)"),
    "chromium_cr": _("Chromium (Cr)"),
    "lead_pb": _("Lead (Pb)"),
    "copper_cu": _("Copper (Cu)"),
    "tin_sn": _("Tin (Sn)"),
    "aluminum_al": _("Aluminum (Al)"),
    "nickel_ni": _("Nickel (Ni)"),
    "silver_ag": _("Silver (Ag)"),
    "silicon_si": _("Silicon (Si)"),
    "boron_b": _("Boron (B)"),
    "sodium_na": _("Sodium (Na)"),
    "magnesium_mg": _("Magnesium (Mg)"),
    "potassium_k": _("Potassium (K)"),
    "molybdenum_mo": _("Molybdenum (Mo)"),
    "titanium_ti": _("Titanium (Ti)"),
    "vanadium_v": _("Vanadium (V)"),
    "manganese_mn": _("Manganese (Mn)"),
    "phosphorus_p": _("Phosphorus (P)"),
    "zinc_zn": _("Zinc (Zn)"),
    "calcium_ca": _("Calcium (Ca)"),
    "barium_ba": _("Barium (Ba)"),
    "cadmium_cd": _("Cadmium (Cd)"),
    "viscosity_40c": _("Viscosity @40°C"),
    "viscosity_100c": _("Viscosity @100°C"),
    "viscosity_index": _("Viscosity Index"),
    "tbn": _("TBN"),
    "tan": _("TAN"),
    "oxidation": _("Oxidation"),
    "nitration": _("Nitration"),
    "sulfation": _("Sulfation"),
    "fuel_dilution": _("Fuel Dilution"),
    "water_ftir": _("Water (FTIR)"),
    "glycol": _("Glycol"),
    "soot": _("Soot"),
    "pq_index": _("PQ Index"),
}

# Labels and colors for the normalized parameter/overall statuses.
STATUS_LABELS: Final[dict[str, Any]] = {
    "normal": _("Normal"),
    "caution": _("Caution"),
    "critical": _("Critical"),
}

STATUS_COLORS: Final[dict[str, str]] = {
    "normal": "#12b76a",
    "caution": "#FFA70B",
    "critical": "#f04438",
}

# Wear metals represented in the radar chart.
WEAR_METALS_RADAR: Final[list[str]] = [
    "iron_fe",
    "copper_cu",
    "aluminum_al",
    "lead_pb",
    "chromium_cr",
    "silicon_si",
]

# Default KPI parameters shown on the overview tab.
DEFAULT_KPI_PARAMETERS: Final[list[str]] = [
    "iron_fe",
    "copper_cu",
    "aluminum_al",
    "silicon_si",
    "viscosity_100c",
    "tbn",
]

# Fallback wear-source descriptions, used only when no threshold in the
# database provides a ``wear_source_description``.
DEFAULT_WEAR_SOURCES: Final[dict[str, Any]] = {
    "iron_fe": _("Wear from cylinder liners, crankshaft, camshaft, and timing gears."),
    "copper_cu": _("Connecting rod/main bearings, bushings, and oil cooler."),
    "aluminum_al": _("Pistons, connecting rod bearings, turbocharger, and oil pump."),
    "silicon_si": _("External contamination (dust/dirt). Check air filters and seals."),
    "sodium_na": _("Coolant ingress or external contamination."),
    "potassium_k": _("Coolant ingress or external contamination."),
    "lead_pb": _("Connecting rod and main bearings (alloy)."),
    "chromium_cr": _("Piston rings, valves, and crankshaft."),
}

# Tabs available for the component analysis page.
DEFAULT_TABS: Final[list[dict[str, Any]]] = [
    {"id": "overview", "label": _("Overview")},
    {"id": "wear", "label": _("Wear")},
    {"id": "condition", "label": _("Condition")},
    {"id": "trends", "label": _("Trends")},
    {"id": "advanced", "label": _("Advanced")},
]


def get_component_type_key(component_type_name: str | None) -> str:
    """Return a normalized key derived from the component type name.

    The key is the trimmed, upper-cased type name. Deriving it directly from
    the configured name avoids maintaining an external taxonomy.

    Args:
        component_type_name: The component type name (may be empty/None).

    Returns:
        The normalized key, or an empty string when no name is provided.
    """
    if not component_type_name:
        return ""
    return component_type_name.strip().upper()


def get_kpi_parameters_for_component_type(
    component_type_name: str | None,
) -> list[str]:
    """Return the KPI parameter keys for a component type.

    The default KPI set is used for every component type.

    Args:
        component_type_name: The component type name (unused).

    Returns:
        List of parameter keys.
    """
    return list(DEFAULT_KPI_PARAMETERS)


def get_wear_sources_for_component_type(
    component_type_name: str | None,
) -> dict[str, Any]:
    """Return fallback wear-source descriptions for a component type.

    Args:
        component_type_name: The component type name (unused).

    Returns:
        Mapping of parameter key to wear source description.
    """
    return dict(DEFAULT_WEAR_SOURCES)


def get_tabs_for_component_type(
    component_type_name: str | None,
) -> list[dict[str, Any]]:
    """Return the analysis tabs available for a component type.

    Args:
        component_type_name: The component type name (unused).

    Returns:
        List of tab dictionaries with ``id`` and ``label``.
    """
    return [dict(tab) for tab in DEFAULT_TABS]
