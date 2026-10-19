"""Constants for the users app."""

from typing import Final

from django.utils.translation import gettext_lazy as _

#: App labels whose permissions can be granted through the role matrix.
#:
#: The order is the dashboard menu order, not the alphabetical app-label order,
#: so the permission matrix reads like the rest of the interface. Django and
#: third-party apps are deliberately excluded: their permissions belong to the
#: framework, not to the client's dashboard.
ROLE_PERMISSION_MODULES: Final[dict[str, str]] = {
    "equipment": _("Equipment"),
    "reports": _("Reports"),
    "alerts": _("Alerts"),
    "organizations": _("Clients"),
    "users": _("Accounts and access"),
}

#: Human-readable labels for the standard CRUD permission prefixes.
PERMISSION_ACTIONS: Final[dict[str, str]] = {
    "view": _("View"),
    "add": _("Create"),
    "change": _("Edit"),
    "delete": _("Delete"),
}
