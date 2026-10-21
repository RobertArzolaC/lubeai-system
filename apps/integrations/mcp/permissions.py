"""Authorization helpers shared by the MCP tools.

OAuth establishes *who* is calling; these helpers enforce *what data* the
caller may see. A user without an organization is rejected instead of falling
back to the unrestricted behaviour used by some dashboard flows, because an
MCP token is a long-lived credential and a silent global scope would be a
privilege escalation.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django_mcpz.server import ToolError

from apps.organizations import models as organization_models
from apps.organizations import scoping


def request_organization(
    request,
) -> organization_models.Organization | None:
    """Return the organization that scopes the caller's data.

    Args:
        request: The current MCP request, with ``request.user`` set by OAuth.

    Returns:
        The user's organization, or ``None`` for a superuser.

    Raises:
        ToolError: When a non-superuser has no organization assigned.
    """
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise ToolError("La conexión no está autenticada.")
    organization = getattr(user, "organization", None)
    if organization is None and not getattr(user, "is_superuser", False):
        raise ToolError(
            "Tu usuario no tiene una organización asignada. "
            "Contacta al administrador de tu cuenta."
        )
    return organization


def scoped_queryset(
    request, queryset: QuerySet, field: str = "organization"
) -> QuerySet:
    """Restrict ``queryset`` to the organizations visible to the caller.

    Args:
        request: The current MCP request.
        queryset: The base queryset.
        field: The tenancy lookup on the queryset model (may use ``__``).

    Returns:
        The scoped queryset.
    """
    request_organization(request)
    return scoping.scope_queryset(queryset, request.user, field=field)
