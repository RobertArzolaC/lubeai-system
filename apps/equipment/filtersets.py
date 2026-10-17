from typing import ClassVar

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.equipment import models
from apps.organizations import models as organization_models
from apps.organizations import scoping


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
        model = models.Branch
        fields: ClassVar[list[str]] = ["name_search", "organization", "is_active"]

    def __init__(self, *args, **kwargs):
        """Scope the organization choices to the request user."""
        super().__init__(*args, **kwargs)
        scoping.scope_organization_filter(self)

    def filter_by_name(self, queryset, name, value):
        """Filter branches by name or address."""
        return queryset.filter(Q(name__icontains=value) | Q(address__icontains=value))


class MachineFilter(django_filters.FilterSet):
    """FilterSet for Machine model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    organization = django_filters.ModelChoiceFilter(
        queryset=organization_models.Organization.objects.all(),
        empty_label=_("All Clients"),
        label=_("Client"),
    )
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
        fields: ClassVar[list[str]] = [
            "name_search",
            "organization",
            "branch",
            "fleet",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        """Scope branch/fleet/organization choices to the user's organizations."""
        super().__init__(*args, **kwargs)
        scoping.scope_choices(
            self,
            {
                "branch": models.Branch.objects.filter(is_active=True),
                "fleet": models.Fleet.objects.filter(is_active=True),
            },
        )
        scoping.scope_organization_filter(self)

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
        model = models.ComponentType
        fields: ClassVar[list[str]] = ["name_search", "organization", "is_active"]

    def __init__(self, *args, **kwargs):
        """Scope the organization choices to the request user."""
        super().__init__(*args, **kwargs)
        scoping.scope_organization_filter(self)

    def filter_by_name(self, queryset, name, value):
        """Filter component types by name or description."""
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )
