from typing import ClassVar

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.alerts import models
from apps.alerts.services.alert_service import AlertService
from apps.equipment import models as equipment_models
from apps.reports import models as report_models


class AlertForm(forms.ModelForm):
    """Form for editing generated alerts.

    System-managed fields (``dedup_key``, ``sent_channels`` and the lifecycle
    timestamps) are excluded; the acknowledgement/resolution timestamps are
    derived from the selected ``status`` by :class:`AlertService`.
    """

    class Meta:
        model = models.Alert
        fields: ClassVar[list[str]] = [
            "machine",
            "component",
            "report",
            "parameter",
            "category",
            "severity",
            "status",
            "value",
            "warning_limit",
            "critical_limit",
            "unit",
            "rule_type",
            "detected_at",
        ]
        widgets: ClassVar[dict] = {
            "machine": forms.Select(attrs={"class": "form-select"}),
            "component": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
            "parameter": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "warning_limit": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "critical_limit": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "unit": forms.TextInput(attrs={"class": "form-control"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "detected_at": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs) -> None:
        """Limit relation choices to active records and store the actor.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            user: User performing the change, used for ``acknowledged_by``.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, **kwargs)
        self.user = user
        self._service = AlertService()
        self.fields["machine"].queryset = equipment_models.Machine.objects.filter(
            is_active=True
        )
        self.fields["component"].queryset = equipment_models.Component.objects.filter(
            is_active=True
        ).select_related("type")
        self.fields["report"].queryset = report_models.Report.objects.filter(
            is_active=True
        ).select_related("machine", "component")

    def clean(self) -> dict:
        """Validate that warning and critical limits are distinct.

        Returns:
            The cleaned form data.

        Raises:
            ValidationError: If both limits are equal.
        """
        cleaned_data = super().clean()
        warning_limit = cleaned_data.get("warning_limit")
        critical_limit = cleaned_data.get("critical_limit")

        if (
            warning_limit is not None
            and critical_limit is not None
            and warning_limit == critical_limit
        ):
            self.add_error(
                "critical_limit",
                _("The critical limit must differ from the warning limit."),
            )

        return cleaned_data

    def save(self, commit: bool = True) -> models.Alert:
        """Persist the alert, syncing its lifecycle timestamps.

        Args:
            commit: Whether to write the instance to the database.

        Returns:
            The saved :class:`~apps.alerts.models.Alert` instance.
        """
        alert = super().save(commit=False)
        self._service.apply_status_transition(alert, self.user)
        if commit:
            alert.save()
            self.save_m2m()
        return alert
