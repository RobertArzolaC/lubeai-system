"""Central registry of translatable breadcrumb labels.

Breadcrumbs are derived dynamically from the resolved URL name. Keeping the
labels here (instead of deriving them from raw URL tokens) makes them
translatable via gettext and consistent with the sidebar navigation.
"""

from typing import Final

from django.utils.translation import gettext_lazy as _

# Entity labels used for the ``*_list`` URLs (and as the parent crumb of the
# entity actions).
ENTITY_LABELS: Final[dict[str, str]] = {
    "machine": _("Machines"),
    "branch": _("Branches"),
    "fleet": _("Fleets"),
    "component_type": _("Component Types"),
    "laboratory": _("Laboratories"),
    "report": _("Reports"),
    "analysisthreshold": _("Thresholds"),
    "alert": _("Alerts"),
    "account": _("Accounts"),
}

# Action labels appended after the entity crumb.
ACTION_LABELS: Final[dict[str, str]] = {
    "detail": _("Detail"),
    "create": _("Create"),
    "update": _("Update"),
    "delete": _("Delete"),
}

# Pages that are not tied to an entity list.
SPECIAL_LABELS: Final[dict[str, str]] = {
    "index": _("Dashboard"),
    "component_analysis": _("Component Analysis"),
    "report_export": _("Export"),
    "profile": _("Profile"),
    "settings": _("Settings"),
}


def resolve_breadcrumb_label(url_name: str) -> str | None:
    """Return the translatable label for a resolved ``url_name``.

    The URL name is split into an entity key and an action suffix so that
    multi-word entities (e.g. ``component_type_detail``) resolve correctly.

    Args:
        url_name: The name of the resolved URL pattern.

    Returns:
        The label for the breadcrumb, or ``None`` when the URL is not part of
        the navigable hierarchy (API endpoints, unknown routes, ...).
    """
    if not url_name:
        return None

    if url_name in SPECIAL_LABELS:
        return SPECIAL_LABELS[url_name]

    for action, label in ACTION_LABELS.items():
        suffix = f"_{action}"
        if url_name.endswith(suffix):
            entity = url_name[: -len(suffix)]
            return label if entity in ENTITY_LABELS else None

    if url_name.endswith("_list"):
        entity = url_name[: -len("_list")]
        if entity in ENTITY_LABELS:
            return ENTITY_LABELS[entity]

    return None
