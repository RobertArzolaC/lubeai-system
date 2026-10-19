"""FilterSets for the platform's tenant console."""

from __future__ import annotations

from typing import ClassVar

import django_filters
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from apps.tenancy import choices, models


class TenantFilter(django_filters.FilterSet):
    """FilterSet for the shared :class:`models.Tenant` registry.

    The registry is not scoped by organization: the operations tenant is the
    platform operator and sees every client.
    """

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    kind = django_filters.ChoiceFilter(
        choices=choices.TenantKind.choices,
        empty_label=_("All kinds"),
        label=_("Kind"),
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
        model = models.Tenant
        fields: ClassVar[list[str]] = ["name_search", "kind", "is_active"]

    def filter_by_name(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        """Filter tenants by name or slug."""
        return queryset.filter(Q(name__icontains=value) | Q(slug__icontains=value))
