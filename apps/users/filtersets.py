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
