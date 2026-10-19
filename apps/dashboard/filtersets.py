"""Filters for the dashboard app."""

from typing import ClassVar

import django_filters
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from apps.core import widgets as core_widgets
from apps.dashboard import search as dashboard_search
from apps.equipment import models as equipment_models
from apps.organizations import scoping
from apps.reports import models as reports_models


class DashboardFilter(django_filters.FilterSet):
    """Filter oil analysis samples by text, year, fleet, machine and component."""

    search = django_filters.CharFilter(
        method="filter_by_search",
        label=_("Search"),
    )
    year = django_filters.NumberFilter(
        field_name="sample_date",
        lookup_expr="year",
        label=_("Year"),
    )
    fleet = django_filters.ModelChoiceFilter(
        field_name="machine__fleet",
        queryset=equipment_models.Fleet.objects.filter(is_active=True),
        label=_("Fleet"),
    )
    machine = django_filters.ModelChoiceFilter(
        field_name="machine",
        queryset=equipment_models.Machine.objects.filter(is_active=True),
        label=_("Machine"),
        widget=core_widgets.ThemeModelSelect2(
            url="apps.equipment:autocomplete_machine",
            attrs={
                "class": "filter-control",
                "data-placeholder": _("Select Machine"),
                "data-allow-clear": "true",
            },
        ),
    )
    component = django_filters.ModelChoiceFilter(
        field_name="component",
        queryset=equipment_models.Component.objects.filter(is_active=True),
        label=_("Component"),
        widget=core_widgets.ThemeModelSelect2(
            url="apps.equipment:autocomplete_component",
            forward=["machine"],
            attrs={
                "class": "filter-control",
                "data-placeholder": _("Select Component"),
                "data-allow-clear": "true",
            },
        ),
    )

    class Meta:
        model = reports_models.Report
        fields: ClassVar[list[str]] = [
            "search",
            "year",
            "fleet",
            "machine",
            "component",
        ]

    def __init__(self, *args, **kwargs) -> None:
        """Scope fleet/machine/component choices to the user's subtree."""
        super().__init__(*args, **kwargs)
        scoping.scope_choices(
            self,
            {
                "fleet": equipment_models.Fleet.objects.filter(is_active=True),
                "machine": equipment_models.Machine.objects.filter(is_active=True),
                "component": equipment_models.Component.objects.filter(is_active=True),
            },
        )
        self._narrow_component_choices()

    def _narrow_component_choices(self) -> None:
        """Limit component choices to the machine selected in the request.

        A component is only meaningful next to its machine: without a valid
        machine the choices are empty, so a crafted request cannot combine a
        component with a different machine.
        """
        if self.data is None:
            return

        queryset = self.filters["component"].field.queryset
        try:
            machine_id = int(self.data.get("machine"))
        except (TypeError, ValueError):
            queryset = queryset.none()
        else:
            queryset = queryset.filter(machine_id=machine_id)
        self.filters["component"].field.queryset = queryset

    def filter_by_search(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        """Filter samples by their identifiers, machine or component type.

        Args:
            queryset: The base queryset to filter.
            name: The filter name (unused).
            value: Text typed in the dashboard's search box.

        Returns:
            The narrowed queryset.
        """
        return queryset.filter(
            dashboard_search.build_search_q(
                dashboard_search.REPORT_SEARCH_FIELDS, value
            )
        )
