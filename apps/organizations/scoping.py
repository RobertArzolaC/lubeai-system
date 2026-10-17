"""Queryset scoping helpers based on the tenancy tree.

A user only sees objects that belong to the organizations in its own subtree
(its organization and its descendants). Platform-level users (superusers, or
users belonging to a ``PLATFORM`` organization) are unrestricted.

Ruling: a user without an organization is treated as unrestricted so the
existing single-tenant data and tests keep working; new users are expected to
be assigned to an organization. Cost if wrong: an unassigned user would see
all data instead of none.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import FieldDoesNotExist
from django.db.models import QuerySet

from apps.organizations import choices


def user_visible_organization_ids(user) -> set[int] | None:
    """Return the organization ids ``user`` may see.

    Args:
        user: The request user (may be anonymous).

    Returns:
        ``None`` when access is unrestricted, otherwise the set of visible
        organization ids (possibly empty).
    """
    if user is None:
        return None
    if not getattr(user, "is_authenticated", False):
        return set()
    if getattr(user, "is_superuser", False):
        return None

    organization = getattr(user, "organization", None)
    if organization is None:
        return None
    if organization.kind == choices.OrganizationKind.PLATFORM:
        return None

    return set(
        organization.descendants(include_self=True).values_list("id", flat=True)
    )


def request_user(request: Any) -> Any:
    """Return the user for ``request``, or ``None`` when there is no request.

    Used by views that may be instantiated without a request (e.g. in tests).
    """
    return getattr(request, "user", None) if request is not None else None


def scope_queryset(queryset: QuerySet, user, field: str = "organization") -> QuerySet:
    """Restrict ``queryset`` to the organizations visible to ``user``.

    Models without the tenancy field are returned unchanged.

    Args:
        queryset: The queryset to scope.
        user: The request user.
        field: Name of the tenancy FK on the model.

    Returns:
        The scoped queryset.
    """
    visible_ids = user_visible_organization_ids(user)
    if visible_ids is None:
        return queryset

    root_field = field.split("__")[0]
    try:
        queryset.model._meta.get_field(root_field)
    except FieldDoesNotExist:
        return queryset

    return queryset.filter(**{f"{field}_id__in": visible_ids})


def scope_choices(filterset, mapping: dict) -> None:
    """Scope the given ``ModelChoiceFilter`` querysets of a FilterSet.

    No-op when the FilterSet was built without a request (e.g. direct use in
    tests), preserving the declared querysets.

    Args:
        filterset: The bound FilterSet instance.
        mapping: Mapping of filter name to its base queryset.
    """
    request = getattr(filterset, "request", None)
    if request is None:
        return
    for name, queryset in mapping.items():
        if name in filterset.filters:
            filterset.filters[name].queryset = scope_queryset(queryset, request.user)


def visible_organizations(user) -> QuerySet:
    """Return the organizations ``user`` may act upon.

    Unrestricted users get every organization; everyone else gets their own
    subtree (their organization and its descendants).
    """
    from apps.organizations import models as organization_models

    queryset = organization_models.Organization.objects.all()
    visible_ids = user_visible_organization_ids(user)
    if visible_ids is None:
        return queryset
    return queryset.filter(pk__in=visible_ids)


def is_organization_visible(user, organization) -> bool:
    """Return ``True`` when ``user`` may act on ``organization``."""
    if organization is None:
        return False
    visible_ids = user_visible_organization_ids(user)
    if visible_ids is None:
        return True
    return organization.pk in visible_ids


def can_choose_organization(user) -> bool:
    """Return ``True`` when ``user`` may pick among several organizations.

    This is the single predicate that decides whether the "Client" column,
    filter and form field are shown.
    """
    visible_ids = user_visible_organization_ids(user)
    return visible_ids is None or len(visible_ids) > 1


def scope_organization_filter(filterset, name: str = "organization") -> None:
    """Scope (or drop) a FilterSet's organization filter for its request user.

    No-op when the FilterSet was built without a request (e.g. direct use in
    tests), preserving the declared queryset.

    Args:
        filterset: The bound FilterSet instance.
        name: Name of the organization filter on the FilterSet.
    """
    if name not in filterset.filters:
        return
    request = getattr(filterset, "request", None)
    if request is None:
        return
    if not can_choose_organization(request.user):
        del filterset.filters[name]
        return
    filterset.filters[name].queryset = visible_organizations(request.user)
