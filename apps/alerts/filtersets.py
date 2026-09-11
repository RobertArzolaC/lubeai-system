from typing import ClassVar

import django_filters
from django import forms
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from apps.alerts import choices, models
from apps.equipment import models as equipment_models
from apps.reports import choices as report_choices


class AlertFilter(django_filters.FilterSet):
    """FilterSet for the Alert model."""

    search = django_filters.CharFilter(method="filter_by_search", label=_("Search"))
    severity = django_filters.ChoiceFilter(
        choices=choices.AlertSeverity.choices,
        empty_label=_("All Severities"),
        label=_("Severity"),
    )
    status = django_filters.ChoiceFilter(
        choices=choices.AlertStatus.choices,
        empty_label=_("All Statuses"),
        label=_("Status"),
    )
    category = django_filters.ChoiceFilter(
        choices=report_choices.Category.choices,
        empty_label=_("All Categories"),
        label=_("Category"),
    )
    machine = django_filters.ModelChoiceFilter(
        queryset=equipment_models.Machine.objects.filter(is_active=True),
        empty_label=_("All Machines"),
        label=_("Machine"),
    )
    component = django_filters.ModelChoiceFilter(
        queryset=equipment_models.Component.objects.filter(is_active=True),
        empty_label=_("All Components"),
        label=_("Component"),
    )
    detected_after = django_filters.DateFilter(
        field_name="detected_at",
        lookup_expr="date__gte",
        label=_("Detected After"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    detected_before = django_filters.DateFilter(
        field_name="detected_at",
        lookup_expr="date__lte",
        label=_("Detected Before"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta:
        model = models.Alert
        fields: ClassVar[list[str]] = [
            "search",
            "severity",
            "status",
            "category",
            "machine",
            "component",
            "detected_after",
            "detected_before",
        ]

    def filter_by_search(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        """Filter alerts by dedup key, machine or component name."""
        return queryset.filter(
            Q(dedup_key__icontains=value)
            | Q(machine__name__icontains=value)
            | Q(component__type__name__icontains=value)
        )
