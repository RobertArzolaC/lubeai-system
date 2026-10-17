"""FilterSets for the organizations app."""

from __future__ import annotations

from typing import ClassVar

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.organizations import choices, models, scoping


class OrganizationFilter(django_filters.FilterSet):
    """FilterSet for the :class:`models.Organization` model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    kind = django_filters.ChoiceFilter(
        choices=choices.OrganizationKind.choices,
        empty_label=_("All kinds"),
        label=_("Kind"),
    )
    parent = django_filters.ModelChoiceFilter(
        queryset=models.Organization.objects.all(),
        empty_label=_("All parents"),
        label=_("Parent"),
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
        model = models.Organization
        fields: ClassVar[list[str]] = ["name_search", "kind", "parent", "is_active"]

    def __init__(self, *args, **kwargs) -> None:
        """Scope the parent choices to the request user's subtree."""
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        if request is not None and "parent" in self.filters:
            self.filters["parent"].queryset = scoping.visible_organizations(
                request.user
            )

    def filter_by_name(self, queryset, name, value):
        """Filter organizations by name, slug or code."""
        return queryset.filter(
            Q(name__icontains=value)
            | Q(slug__icontains=value)
            | Q(code__icontains=value)
        )
