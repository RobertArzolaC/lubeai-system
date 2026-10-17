from typing import ClassVar

from constance import config
from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from apps.core import widgets as core_widgets
from apps.core.mixins import OrganizationScopeFormMixin
from apps.equipment import constants, models
from apps.organizations import scoping


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


class BranchForm(OrganizationScopeFormMixin, forms.ModelForm):
    """Form for creating and updating branches."""

    class Meta:
        model = models.Branch
        fields: ClassVar[list[str]] = [
            "organization",
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

    def __init__(self, *args, user=None, **kwargs) -> None:
        """Scope the organization choices to the acting user.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            user: The acting user, used to scope the organization choices.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, user=user, **kwargs)


class MachineForm(OrganizationScopeFormMixin, forms.ModelForm):
    """Form for creating and updating machines."""

    class Meta:
        model = models.Machine
        fields: ClassVar[list[str]] = [
            "organization",
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

    def __init__(self, *args, user=None, **kwargs) -> None:
        """Hide the fleet field when disabled and scope relation choices.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            user: The acting user, used to scope branch/fleet choices.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, user=user, **kwargs)
        if not config.ENABLE_FLEET:
            self.fields.pop("fleet", None)

        if user is not None:
            self.fields["branch"].queryset = scoping.scope_queryset(
                models.Branch.objects.filter(is_active=True), user
            )
            if "fleet" in self.fields:
                self.fields["fleet"].queryset = scoping.scope_queryset(
                    models.Fleet.objects.filter(is_active=True), user
                )

    def clean(self):
        """Keep the machine's client coherent with its branch's client.

        Only applies when the Client field is present: without it (no user, or
        a leaf user) the form keeps its legacy behaviour untouched.
        """
        cleaned = super().clean()
        if "organization" not in self.fields:
            return cleaned
        organization = cleaned.get("organization") or getattr(
            self.instance, "organization", None
        )
        branch = cleaned.get("branch")
        if branch is None:
            return cleaned
        if organization is None:
            cleaned["organization"] = branch.organization
        elif (
            branch.organization_id is not None
            and branch.organization_id != organization.pk
        ):
            self.add_error(
                "branch",
                _("The branch does not belong to the selected client."),
            )
        return cleaned


class ComponentTypeForm(OrganizationScopeFormMixin, forms.ModelForm):
    """Form for creating and updating component types."""

    class Meta:
        model = models.ComponentType
        fields: ClassVar[list[str]] = [
            "organization",
            "name",
            "description",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, user=None, **kwargs) -> None:
        """Scope the organization choices to the acting user.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            user: The acting user, used to scope the organization choices.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, user=user, **kwargs)


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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        types = models.ComponentType.objects.filter(is_active=True)
        if user is not None:
            types = scoping.scope_queryset(types, user)
        self.fields["type"].queryset = types
        self.fields["type"].empty_label = _("Select Component Type")


ComponentFormSet = inlineformset_factory(
    models.Machine,
    models.Component,
    form=ComponentForm,
    extra=1,
    can_delete=True,
)
