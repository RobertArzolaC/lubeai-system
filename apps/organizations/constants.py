"""Constants for the organizations app.

Capabilities are per organization, defaulted from its tenant ``kind`` and
overridable through the ``Organization.capabilities`` JSON field. The global
constance flags remain a master override for the whole instance.
"""

from typing import Any, Final

# Branding slots resolved (with inheritance) by ``Organization.get_branding``.
BRANDING_SLOTS: Final[tuple[str, ...]] = (
    "primary_color",
    "chart_primary",
    "chart_success",
    "chart_warning",
    "chart_danger",
    "chart_info",
    "chart_dark",
)

# Default palette used when no organization overrides a slot.
DEFAULT_BRANDING: Final[dict[str, str]] = {
    "primary_color": "#465fff",
    "chart_primary": "#465fff",
    "chart_success": "#12b76a",
    "chart_warning": "#FFA70B",
    "chart_danger": "#f04438",
    "chart_info": "#0ba5ec",
    "chart_dark": "#181c32",
}

# Capabilities enabled by default for each organization kind.
DEFAULT_CAPABILITIES: Final[dict[str, dict[str, Any]]] = {
    "platform": {
        "labs": True,
        "fleet": True,
        "thresholds": True,
        "analysis": True,
        "alerts": True,
    },
    "lab": {
        "labs": False,
        "fleet": False,
        "thresholds": True,
        "analysis": True,
        "alerts": True,
    },
    "intermediary": {
        "labs": False,
        "fleet": False,
        "thresholds": False,
        "analysis": True,
        "alerts": True,
    },
    "final": {
        "labs": False,
        "fleet": False,
        "thresholds": False,
        "analysis": True,
        "alerts": True,
    },
}
