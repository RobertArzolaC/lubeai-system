from typing import ClassVar

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.equipment import models as equipment_models
from apps.reports import models


class LaboratoryForm(forms.ModelForm):
    """Form for creating and updating laboratories."""

    class Meta:
        model = models.Laboratory
        fields: ClassVar[list[str]] = [
            "name",
            "code",
            "description",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ReportForm(forms.ModelForm):
    """Form for creating and updating reports."""

    class Meta:
        model = models.Report
        fields: ClassVar[list[str]] = [
            "laboratory",
            "machine",
            "component",
            "lab_number",
            "lubricant",
            "lubricant_hours",
            "lubricant_kms",
            "machine_hours",
            "machine_kms",
            "serial_number_code",
            "sample_date",
            "per_number",
            "reception_date",
            "report_date",
            "status",
            "condition",
            "filter_change",
            "oil_change",
            "others",
            "recommendations",
            "component_hour_meter",
            "previous_hour_meter",
            "sampling_type",
            "pm_position",
            "action_required",
            "turnaround_days",
            "notes",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "laboratory": forms.Select(attrs={"class": "form-select"}),
            "machine": forms.Select(attrs={"class": "form-select"}),
            "component": forms.Select(attrs={"class": "form-select"}),
            "lab_number": forms.TextInput(attrs={"class": "form-control"}),
            "lubricant": forms.TextInput(attrs={"class": "form-control"}),
            "lubricant_hours": forms.NumberInput(attrs={"class": "form-control"}),
            "lubricant_kms": forms.NumberInput(attrs={"class": "form-control"}),
            "machine_hours": forms.NumberInput(attrs={"class": "form-control"}),
            "machine_kms": forms.NumberInput(attrs={"class": "form-control"}),
            "serial_number_code": forms.TextInput(attrs={"class": "form-control"}),
            "sample_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "per_number": forms.TextInput(attrs={"class": "form-control"}),
            "reception_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "report_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "filter_change": forms.TextInput(attrs={"class": "form-control"}),
            "oil_change": forms.TextInput(attrs={"class": "form-control"}),
            "others": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "recommendations": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "component_hour_meter": forms.NumberInput(attrs={"class": "form-control"}),
            "previous_hour_meter": forms.NumberInput(attrs={"class": "form-control"}),
            "sampling_type": forms.TextInput(attrs={"class": "form-control"}),
            "pm_position": forms.TextInput(attrs={"class": "form-control"}),
            "action_required": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "turnaround_days": forms.NumberInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        """Limit relation choices to active records and mark required fields."""
        super().__init__(*args, **kwargs)
        self.fields["machine"].required = True
        self.fields["component"].required = True
        self.fields["lab_number"].required = True
        self.fields["sample_date"].required = True

        self.fields["laboratory"].queryset = models.Laboratory.objects.filter(
            is_active=True
        )
        self.fields["machine"].queryset = equipment_models.Machine.objects.filter(
            is_active=True
        )
        self.fields["component"].queryset = equipment_models.Component.objects.filter(
            is_active=True
        ).select_related("type")


class AnalysisThresholdForm(forms.ModelForm):
    """Form for creating and updating AnalysisThreshold instances."""

    class Meta:
        model = models.AnalysisThreshold
        fields: ClassVar[list[str]] = [
            "component_type",
            "category",
            "parameter",
            "warning_limit",
            "critical_limit",
            "unit",
            "is_inverse",
            "wear_source_description",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "component_type": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "parameter": forms.Select(attrs={"class": "form-select"}),
            "warning_limit": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "critical_limit": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "unit": forms.TextInput(attrs={"class": "form-control"}),
            "is_inverse": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "wear_source_description": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        """Limit the component type choices to active records."""
        super().__init__(*args, **kwargs)
        self.fields[
            "component_type"
        ].queryset = equipment_models.ComponentType.objects.filter(is_active=True)

    def clean(self) -> dict:
        """
        Validate threshold limits.

        Ensures warning_limit is less than critical_limit for normal logic,
        and the reverse for inverse logic.

        Returns:
            dict: Cleaned form data

        Raises:
            ValidationError: If limit validation fails
        """
        cleaned_data = super().clean()
        warning_limit = cleaned_data.get("warning_limit")
        critical_limit = cleaned_data.get("critical_limit")
        is_inverse = cleaned_data.get("is_inverse")

        if warning_limit is not None and critical_limit is not None:
            if is_inverse:
                # For inverse logic (additives), critical should be lower
                if warning_limit < critical_limit:
                    raise forms.ValidationError(
                        _(
                            "For inverse logic, warning limit should be "
                            "greater than or equal to critical limit."
                        )
                    )
            else:
                # For normal logic, warning should be lower
                if warning_limit > critical_limit:
                    raise forms.ValidationError(
                        _(
                            "Warning limit should be less than or equal "
                            "to critical limit."
                        )
                    )

        return cleaned_data
