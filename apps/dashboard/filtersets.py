"""Filters for the dashboard app."""

from typing import ClassVar

import django_filters
from django.utils.translation import gettext_lazy as _

from apps.equipment import models as equipment_models
from apps.reports import models as reports_models


class DashboardFilter(django_filters.FilterSet):
    """Filter oil analysis samples by year, fleet, machine and component type."""

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
    )
    component_type = django_filters.ModelChoiceFilter(
        field_name="component__type",
        queryset=equipment_models.ComponentType.objects.filter(is_active=True),
        label=_("Component Type"),
    )

    class Meta:
        model = reports_models.Report
        fields: ClassVar[list[str]] = ["year", "fleet", "machine", "component_type"]
