from typing import ClassVar

import django_filters
from constance import config
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from apps.core import widgets as core_widgets
from apps.equipment import models as equipment_models
from apps.organizations import models as organization_models
from apps.organizations import scoping
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
    organization = django_filters.ModelChoiceFilter(
        queryset=organization_models.Organization.objects.all(),
        empty_label=_("All Clients"),
        label=_("Client"),
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
        widget=core_widgets.ThemeModelSelect2(
            url="apps.equipment:autocomplete_machine",
            attrs={
                "data-placeholder": _("Select Machine"),
                "data-allow-clear": "true",
            },
        ),
    )
    component = django_filters.ModelChoiceFilter(
        queryset=equipment_models.Component.objects.filter(is_active=True),
        empty_label=_("All Components"),
        label=_("Component"),
        widget=core_widgets.ThemeModelSelect2(
            url="apps.equipment:autocomplete_component",
            forward=["machine"],
            attrs={
                "data-placeholder": _("Select Component"),
                "data-allow-clear": "true",
            },
        ),
    )
    condition = django_filters.ChoiceFilter(
        field_name="condition",
        empty_label=_("All Conditions"),
        label=_("Condition"),
        choices=choices.ReportCondition.choices,
    )

    class Meta:
        model = models.Report
        fields: ClassVar[list[str]] = [
            "lab_number_search",
            "organization",
            "laboratory",
            "machine",
            "component",
            "condition",
        ]

    def __init__(self, *args, **kwargs) -> None:
        """Hide the laboratory filter when the flag is disabled."""
        super().__init__(*args, **kwargs)
        if not config.ENABLE_LABS:
            self.filters.pop("laboratory", None)
        scoping.scope_choices(
            self,
            {
                "machine": equipment_models.Machine.objects.filter(is_active=True),
                "component": equipment_models.Component.objects.filter(is_active=True),
            },
        )
        scoping.scope_organization_filter(self, include_self=False)
        self._narrow_component_choices()

    def _narrow_component_choices(self) -> None:
        """Limit component choices to the machine selected in the request.

        A component only makes sense next to its machine: without a valid
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

    class Meta:
        model = models.Report
        fields: ClassVar[list[str]] = [
            "start_date",
            "end_date",
            "laboratory",
            "machine",
            "component",
            "condition",
        ]

    def __init__(self, *args, **kwargs) -> None:
        """Hide the laboratory filter when the flag is disabled."""
        super().__init__(*args, **kwargs)
        if not config.ENABLE_LABS:
            self.filters.pop("laboratory", None)
        scoping.scope_choices(
            self,
            {
                "machine": equipment_models.Machine.objects.filter(is_active=True),
                "component": equipment_models.Component.objects.filter(is_active=True),
            },
        )


class AnalysisThresholdFilter(django_filters.FilterSet):
    """Filter for AnalysisThreshold model."""

    parameter_search = django_filters.CharFilter(
        method="filter_by_parameter",
        label=_("Search"),
    )
    organization = django_filters.ModelChoiceFilter(
        field_name="component_type__organization",
        queryset=organization_models.Organization.objects.all(),
        empty_label=_("All Clients"),
        label=_("Client"),
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
        fields: ClassVar[list[str]] = [
            "parameter_search",
            "organization",
            "category",
            "is_active",
        ]

    def __init__(self, *args, **kwargs) -> None:
        """Scope the organization filter to the request user."""
        super().__init__(*args, **kwargs)
        scoping.scope_organization_filter(self, include_self=False)

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


class ComponentAnalysisFilter(django_filters.FilterSet):
    """Filter for component analysis."""

    machine = django_filters.ModelChoiceFilter(
        queryset=equipment_models.Machine.objects.filter(is_active=True),
        empty_label=_("Select Machine"),
        label=_("Machine"),
        required=True,
        widget=core_widgets.ThemeModelSelect2(
            url="apps.equipment:autocomplete_machine",
            attrs={
                "data-placeholder": _("Select Machine"),
                "data-allow-clear": "true",
            },
        ),
    )
    component = django_filters.ModelChoiceFilter(
        queryset=equipment_models.Component.objects.filter(is_active=True),
        empty_label=_("Select Component"),
        label=_("Component"),
        required=True,
        widget=core_widgets.ThemeModelSelect2(
            url="apps.equipment:autocomplete_component",
            forward=["machine"],
            attrs={
                "data-placeholder": _("Select Component"),
                "data-allow-clear": "true",
            },
        ),
    )

    class Meta:
        model = models.Report
        fields: ClassVar[list[str]] = ["machine", "component"]

    def __init__(self, *args, **kwargs):
        """Narrow the component choices to the selected machine, if any."""
        super().__init__(*args, **kwargs)

        scoping.scope_choices(
            self,
            {
                "machine": equipment_models.Machine.objects.filter(is_active=True),
                "component": equipment_models.Component.objects.filter(
                    is_active=True
                ).select_related("type"),
            },
        )

        if self.data.get("machine"):
            machine_id = self.data.get("machine")
            self.filters["component"].queryset = scoping.scope_queryset(
                equipment_models.Component.objects.filter(
                    machine_id=machine_id, is_active=True
                ).select_related("type"),
                scoping.request_user(getattr(self, "request", None)),
                field="machine__organization",
            )
