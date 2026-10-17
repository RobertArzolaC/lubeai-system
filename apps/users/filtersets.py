from typing import ClassVar

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.organizations import models as organization_models
from apps.organizations import scoping
from apps.users import models


class AccountFilter(django_filters.FilterSet):
    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    is_active = django_filters.ChoiceFilter(
        field_name="user__is_active",
        empty_label=_("Is Active?"),
        label=_("Status"),
        choices=(
            (True, _("Active")),
            (False, _("Inactive")),
        ),
    )

    class Meta:
        model = models.Account
        fields: ClassVar[list[str]] = ["name_search", "is_active"]

    def filter_by_name(self, queryset, name, value):
        return queryset.filter(
            Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(user__email__icontains=value)
        )


class RoleFilter(django_filters.FilterSet):
    """FilterSet for the tenant-scoped :class:`models.Role` model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    organization = django_filters.ModelChoiceFilter(
        queryset=organization_models.Organization.objects.all(),
        empty_label=_("All Clients"),
        label=_("Client"),
    )
    is_active = django_filters.ChoiceFilter(
        field_name="is_active",
        empty_label=_("Is Active?"),
        label=_("Status"),
        choices=(
            (True, _("Active")),
            (False, _("Inactive")),
        ),
    )

    class Meta:
        model = models.Role
        fields: ClassVar[list[str]] = ["name_search", "organization", "is_active"]

    def __init__(self, *args, **kwargs):
        """Scope the organization choices to the request user."""
        super().__init__(*args, **kwargs)
        scoping.scope_organization_filter(self)

    def filter_by_name(self, queryset, name, value):
        """Filter roles by name or description."""
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class UserFilter(django_filters.FilterSet):
    """FilterSet for the :class:`models.User` model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    organization = django_filters.ModelChoiceFilter(
        queryset=organization_models.Organization.objects.all(),
        empty_label=_("All Clients"),
        label=_("Client"),
    )
    role = django_filters.ModelChoiceFilter(
        queryset=models.Role.objects.filter(is_active=True),
        empty_label=_("All roles"),
        label=_("Role"),
    )
    is_active = django_filters.ChoiceFilter(
        field_name="is_active",
        empty_label=_("Is Active?"),
        label=_("Status"),
        choices=(
            (True, _("Active")),
            (False, _("Inactive")),
        ),
    )

    class Meta:
        model = models.User
        fields: ClassVar[list[str]] = [
            "name_search",
            "organization",
            "role",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        """Scope the organization and role choices to the request user."""
        super().__init__(*args, **kwargs)
        scoping.scope_organization_filter(self)
        request = getattr(self, "request", None)
        if request is not None and "role" in self.filters:
            self.filters["role"].queryset = _visible_roles(request.user)

    def filter_by_name(self, queryset, name, value):
        """Filter users by first/last name or email."""
        return queryset.filter(
            Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
            | Q(email__icontains=value)
        )


def _visible_roles(user):
    """Return the active roles visible to ``user``.

    Args:
        user: The request user.

    Returns:
        A queryset of :class:`~apps.users.models.Role`.
    """
    queryset = models.Role.objects.filter(is_active=True)
    visible_ids = scoping.user_visible_organization_ids(user)
    if visible_ids is None:
        return queryset
    return queryset.filter(organization_id__in=visible_ids)
