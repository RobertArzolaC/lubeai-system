from typing import ClassVar

from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from apps.core import widgets as core_widgets
from apps.equipment import constants, models


class FleetForm(forms.ModelForm):
    """Form for creating and updating fleets."""

    class Meta:
        model = models.Fleet
        fields: ClassVar[list[str]] = [
            "name",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class BranchForm(forms.ModelForm):
    """Form for creating and updating branches."""

    class Meta:
        model = models.Branch
        fields: ClassVar[list[str]] = [
            "name",
            "description",
            "address",
            "zip_code",
            "country",
            "region",
            "subregion",
            "city",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "zip_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": core_widgets.ThemeModelSelect2(
                url="apps.core:autocomplete_country",
                attrs={
                    **constants._LOCATION_WIDGET_ATTRS,
                    "data-placeholder": _("Select country"),
                },
            ),
            "region": core_widgets.ThemeModelSelect2(
                url="apps.core:autocomplete_region",
                forward=["country"],
                attrs={
                    **constants._LOCATION_WIDGET_ATTRS,
                    "data-placeholder": _("Select region"),
                },
            ),
            "subregion": core_widgets.ThemeModelSelect2(
                url="apps.core:autocomplete_subregion",
                forward=["country", "region"],
                attrs={
                    **constants._LOCATION_WIDGET_ATTRS,
                    "data-placeholder": _("Select subregion"),
                },
            ),
            "city": core_widgets.ThemeModelSelect2(
                url="apps.core:autocomplete_city",
                forward=["country", "region", "subregion"],
                attrs={
                    **constants._LOCATION_WIDGET_ATTRS,
                    "data-placeholder": _("Select city"),
                },
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels: ClassVar[dict] = {
            "subregion": _("Subregion"),
        }


class MachineForm(forms.ModelForm):
    """Form for creating and updating machines."""

    class Meta:
        model = models.Machine
        fields: ClassVar[list[str]] = [
            "branch",
            "fleet",
            "name",
            "serial_number",
            "model",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "serial_number": forms.TextInput(attrs={"class": "form-control"}),
            "model": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ComponentTypeForm(forms.ModelForm):
    """Form for creating and updating component types."""

    class Meta:
        model = models.ComponentType
        fields: ClassVar[list[str]] = [
            "name",
            "description",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ComponentForm(forms.ModelForm):
    class Meta:
        model = models.Component
        fields: ClassVar[list[str]] = [
            "type",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].queryset = models.ComponentType.objects.filter(
            is_active=True
        )
        self.fields["type"].empty_label = _("Select Component Type")


ComponentFormSet = inlineformset_factory(
    models.Machine,
    models.Component,
    form=ComponentForm,
    extra=1,
    can_delete=True,
)
