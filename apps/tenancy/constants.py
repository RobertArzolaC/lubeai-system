"""Constants shared by the tenancy registry and its management commands."""

from typing import Final

# Branding slots duplicated from ``apps.organizations.constants``: this app is
# SHARED and must not import a TENANT app, even for a constant tuple.
BRANDING_SLOTS: Final[tuple[str, ...]] = (
    "primary_color",
    "chart_primary",
    "chart_success",
    "chart_warning",
    "chart_danger",
    "chart_info",
    "chart_dark",
)

# Standard component types every provisioned tenant starts with. They are owned
# by the tenant's root organization; a tenant may add its own types later.
DEFAULT_COMPONENT_TYPES: Final[tuple[tuple[str, str], ...]] = (
    ("Motor Principal", "Motor diesel de propulsión"),
    ("Bomba Centrífuga", "Bomba de proceso de fluidos"),
    ("Compresor de Tornillo", "Compresor de aire de tornillo"),
    ("Caja Reductora", "Reductor de velocidad"),
    ("Sistema Hidráulico", "Circuito hidráulico de potencia"),
    ("Turbina de Vapor", "Turbina de vapor auxiliar"),
)

# Password of the demo users created by ``seed_demo_data``.
DEMO_PASSWORD: Final[str] = "Demo12345!"
