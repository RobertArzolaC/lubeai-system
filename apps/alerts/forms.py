from typing import ClassVar

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.alerts import choices, models, validators
from apps.alerts.services.alert_service import AlertService
from apps.equipment import models as equipment_models
from apps.organizations import scoping
from apps.reports import models as report_models


class AlertForm(forms.ModelForm):
    """Form for editing generated alerts.

    System-managed fields (``dedup_key`` and the lifecycle timestamps) are
    excluded; the acknowledgement/resolution timestamps are derived from the
    selected ``status`` by :class:`AlertService`.
    """

    class Meta:
        model = models.Alert
        fields: ClassVar[list[str]] = [
            "machine",
            "component",
            "report",
            "category",
            "severity",
            "status",
            "value",
            "warning_limit",
            "critical_limit",
            "unit",
            "detected_at",
        ]
        widgets: ClassVar[dict] = {
            "machine": forms.Select(attrs={"class": "form-select"}),
            "component": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
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
        machines = equipment_models.Machine.objects.filter(is_active=True)
        components = equipment_models.Component.objects.filter(
            is_active=True
        ).select_related("type")
        reports = report_models.Report.objects.select_related("machine", "component")
        if user is not None:
            machines = scoping.scope_queryset(machines, user)
            components = scoping.scope_queryset(
                components, user, field="machine__organization"
            )
            reports = scoping.scope_queryset(reports, user)
        self.fields["machine"].queryset = machines
        self.fields["component"].queryset = components
        self.fields["report"].queryset = reports

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


class AlertStatusForm(forms.Form):
    """Validate the payload submitted by the status modal.

    Acknowledging or resolving an alert must not require opening (and
    re-submitting) the whole edit form: this form accepts the new ``status``,
    an optional description and an optional evidence file.
    :class:`~apps.alerts.services.alert_service.AlertService` derives the
    lifecycle timestamps from the status and records the history entry.
    """

    status = forms.ChoiceField(
        label=_("Status"),
        choices=choices.AlertStatus.choices,
    )
    note = forms.CharField(
        label=_("Description"),
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 1000}),
    )
    attachment = forms.FileField(
        label=_("Attachment"),
        required=False,
        validators=[validators.validate_alert_attachment],
        widget=forms.ClearableFileInput(attrs={"accept": validators.ATTACHMENT_ACCEPT}),
    )
