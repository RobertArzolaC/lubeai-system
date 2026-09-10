from typing import ClassVar

import django_filters
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from apps.equipment import models as equipment_models
from apps.reports import choices, models


class LaboratoryFilter(django_filters.FilterSet):
    """FilterSet for the Laboratory model."""

    name_search = django_filters.CharFilter(method="filter_by_name", label=_("Search"))
    is_active = django_filters.ChoiceFilter(
        field_name="is_active",
        empty_label=_("All Records"),
        label=_("Record Status"),
        choices=(
            (True, _("Active")),
            (False, _("Inactive")),
        ),
    )

    class Meta:
        model = models.Laboratory
        fields: ClassVar[list[str]] = ["name_search", "is_active"]

    def filter_by_name(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        """Filter laboratories by name, code or description."""
        return queryset.filter(
            Q(name__icontains=value)
            | Q(code__icontains=value)
            | Q(description__icontains=value)
        )


class ReportFilter(django_filters.FilterSet):
    """Filter for reports."""

    lab_number_search = django_filters.CharFilter(
        method="filter_by_lab_number", label=_("Search")
    )
    laboratory = django_filters.ModelChoiceFilter(
        queryset=models.Laboratory.objects.filter(is_active=True),
        empty_label=_("All Laboratories"),
        label=_("Laboratory"),
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
    status = django_filters.ChoiceFilter(
        field_name="status",
        empty_label=_("All Statuses"),
        label=_("Report Status"),
        choices=choices.ReportStatus.choices,
    )
    condition = django_filters.ChoiceFilter(
        field_name="condition",
        empty_label=_("All Conditions"),
        label=_("Condition"),
        choices=choices.ReportCondition.choices,
    )
    is_active = django_filters.ChoiceFilter(
        field_name="is_active",
        empty_label=_("All Records"),
        label=_("Record Status"),
        choices=(
            (True, _("Active")),
            (False, _("Inactive")),
        ),
    )

    class Meta:
        model = models.Report
        fields: ClassVar[list[str]] = [
            "lab_number_search",
            "laboratory",
            "machine",
            "component",
            "status",
            "condition",
            "is_active",
        ]

    def filter_by_lab_number(
        self, queryset: QuerySet, name: str, value: str
    ) -> QuerySet:
        """Filter by lab_number, per_number, serial_number_code or machine name."""
        return queryset.filter(
            Q(lab_number__icontains=value)
            | Q(per_number__icontains=value)
            | Q(serial_number_code__icontains=value)
            | Q(machine__name__icontains=value)
        )


class ReportExportFilter(django_filters.FilterSet):
    """Filter for report exports with date range and component support."""

    start_date = django_filters.DateFilter(
        field_name="sample_date",
        lookup_expr="gte",
        label=_("Start Date"),
    )
    end_date = django_filters.DateFilter(
        field_name="sample_date",
        lookup_expr="lte",
        label=_("End Date"),
    )
    laboratory = django_filters.ModelChoiceFilter(
        queryset=models.Laboratory.objects.filter(is_active=True),
        empty_label=_("All Laboratories"),
        label=_("Laboratory"),
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
    condition = django_filters.ChoiceFilter(
        field_name="condition",
        empty_label=_("All Conditions"),
        label=_("Condition"),
        choices=choices.ReportCondition.choices,
    )
    status = django_filters.ChoiceFilter(
        field_name="status",
        empty_label=_("All Statuses"),
        label=_("Report Status"),
        choices=choices.ReportStatus.choices,
    )

    class Meta:
        model = models.Report
        fields: ClassVar[list[str]] = [
            "start_date",
            "end_date",
            "laboratory",
            "machine",
            "component",
            "condition",
            "status",
        ]


class AnalysisThresholdFilter(django_filters.FilterSet):
    """Filter for AnalysisThreshold model."""

    parameter_search = django_filters.CharFilter(
        method="filter_by_parameter",
        label=_("Search"),
    )
    category = django_filters.ChoiceFilter(
        field_name="category",
        choices=choices.Category.choices,
        empty_label=_("All Categories"),
        label=_("Category"),
    )
    is_active = django_filters.ChoiceFilter(
        field_name="is_active",
        empty_label=_("All Records"),
        label=_("Record Status"),
        choices=(
            (True, _("Active")),
            (False, _("Inactive")),
        ),
    )

    class Meta:
        model = models.AnalysisThreshold
        fields: ClassVar[list[str]] = ["parameter_search", "category", "is_active"]

    def filter_by_parameter(
        self, queryset: QuerySet, name: str, value: str
    ) -> QuerySet:
        """
        Filter thresholds by parameter name or unit.

        Args:
            queryset: The base queryset to filter
            name: The filter name (unused)
            value: The search value

        Returns:
            Filtered queryset
        """
        return queryset.filter(Q(parameter__icontains=value) | Q(unit__icontains=value))
