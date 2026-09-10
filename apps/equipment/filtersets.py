from typing import ClassVar

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.equipment import models


class FleetFilter(django_filters.FilterSet):
    """FilterSet for Fleet model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
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
        model = models.Fleet
        fields: ClassVar[list[str]] = ["name_search", "is_active"]

    def filter_by_name(self, queryset, name, value):
        """Filter fleets by name."""
        return queryset.filter(name__icontains=value)


class BranchFilter(django_filters.FilterSet):
    """FilterSet for Branch model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
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
        model = models.Branch
        fields: ClassVar[list[str]] = ["name_search", "is_active"]

    def filter_by_name(self, queryset, name, value):
        """Filter branches by name or address."""
        return queryset.filter(Q(name__icontains=value) | Q(address__icontains=value))


class MachineFilter(django_filters.FilterSet):
    """FilterSet for Machine model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    branch = django_filters.ModelChoiceFilter(
        queryset=models.Branch.objects.filter(is_active=True),
        empty_label=_("All Branches"),
        label=_("Branch"),
    )
    fleet = django_filters.ModelChoiceFilter(
        queryset=models.Fleet.objects.filter(is_active=True),
        empty_label=_("All Fleets"),
        label=_("Fleet"),
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
        model = models.Machine
        fields: ClassVar[list[str]] = ["name_search", "branch", "fleet", "is_active"]

    def filter_by_name(self, queryset, name, value):
        """Filter machines by name, serial number or model."""
        return queryset.filter(
            Q(name__icontains=value)
            | Q(serial_number__icontains=value)
            | Q(model__icontains=value)
        )


class ComponentTypeFilter(django_filters.FilterSet):
    """FilterSet for ComponentType model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
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
        model = models.ComponentType
        fields: ClassVar[list[str]] = ["name_search", "is_active"]

    def filter_by_name(self, queryset, name, value):
        """Filter component types by name or description."""
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )
