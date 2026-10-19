"""Forms for the platform's tenant console.

The console runs inside the operations tenant and manages the registry in the
``public`` schema. Creating a client is not a plain INSERT: it provisions a
schema, a domain, a ``Site``, a root organization and an administrator, so the
create form is a plain :class:`~django.forms.Form` that delegates to
:func:`apps.tenancy.services.provision_tenant`. Editing a client only touches
the registry row, which is why the update form is a :class:`ModelForm`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.tenancy import choices, constants, models, services

#: Widget attributes shared by the branding colour inputs.
COLOR_WIDGET: dict[str, str] = {
    "class": (
        "w-28 rounded border border-stroke bg-gray py-1.5 px-2 text-xs "
        "text-black focus:border-primary focus-visible:outline-none "
        "dark:border-strokedark dark:bg-meta-4 dark:text-white"
    )
}


class TenantProvisionForm(forms.Form):
    """Provision a new client tenant from the operations console.

    The form validates what can be checked before any DDL (unique slug and free
    domain) and then delegates the provisioning itself to
    :func:`apps.tenancy.services.provision_tenant`, which is idempotent.
    """

    name = forms.CharField(
        label=_("Name"),
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    slug = forms.SlugField(
        label=_("Slug"),
        max_length=63,
        help_text=_("Business identifier; also used as the PostgreSQL schema name"),
    )
    kind = forms.ChoiceField(
        label=_("Kind"),
        choices=choices.TenantKind.choices,
        initial=choices.TenantKind.FINAL,
    )
    domain = forms.CharField(
        label=_("Domain"),
        required=False,
        help_text=_("Host name; defaults to <slug>.<platform domain>"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    admin_email = forms.EmailField(
        label=_("Administrator email"),
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    default_password = forms.CharField(
        label=_("Administrator password"),
        help_text=_("Only applied when the administrator is created"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    capabilities = forms.JSONField(
        label=_("Capabilities"),
        required=False,
        initial=dict,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    primary_color = forms.CharField(
        label=_("Primary color"),
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs=COLOR_WIDGET),
    )
    chart_primary = forms.CharField(
        label=_("Chart primary"),
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs=COLOR_WIDGET),
    )
    chart_success = forms.CharField(
        label=_("Chart success"),
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs=COLOR_WIDGET),
    )
    chart_warning = forms.CharField(
        label=_("Chart warning"),
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs=COLOR_WIDGET),
    )
    chart_danger = forms.CharField(
        label=_("Chart danger"),
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs=COLOR_WIDGET),
    )
    chart_info = forms.CharField(
        label=_("Chart info"),
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs=COLOR_WIDGET),
    )
    chart_dark = forms.CharField(
        label=_("Chart dark"),
        required=False,
        max_length=7,
        widget=forms.TextInput(attrs=COLOR_WIDGET),
    )

    def clean_slug(self) -> str:
        """Reject a slug that is the public schema or already taken."""
        slug = self.cleaned_data["slug"]
        if slug == "public":
            raise forms.ValidationError(_("The public schema is not a client."))
        if models.Tenant.objects.filter(slug=slug).exists():
            raise forms.ValidationError(_("A tenant with that slug already exists."))
        return slug

    def clean_domain(self) -> str:
        """Reject a host name already served by another tenant."""
        domain = (self.cleaned_data.get("domain") or "").strip()
        if domain and models.Domain.objects.filter(domain=domain).exists():
            raise forms.ValidationError(_("That domain is already in use."))
        return domain

    def clean_default_password(self) -> str:
        """Validate the administrator password with Django's validators.

        The password is required: falling back to a repository default would let
        an operator stand up a production client with a publicly known password
        in a single click.

        Returns:
            The validated password.

        Raises:
            ValidationError: If the password fails Django's configured password
                validators (length, common passwords, all-numeric, ...).
        """
        password = self.cleaned_data["default_password"]
        try:
            validate_password(password)
        except ValidationError as error:
            raise forms.ValidationError(error.messages) from error
        return password

    def build_branding(self) -> dict[str, str]:
        """Return the non-empty branding slots selected in the form."""
        return {
            slot: self.cleaned_data[slot]
            for slot in constants.BRANDING_SLOTS
            if self.cleaned_data.get(slot)
        }

    def save(self) -> models.Tenant:
        """Provision the client described by the cleaned data.

        Returns:
            The provisioned tenant.
        """
        data: dict[str, Any] = self.cleaned_data
        return services.provision_tenant(
            slug=data["slug"],
            name=data["name"],
            kind=data["kind"],
            admin_email=data["admin_email"],
            default_password=data["default_password"],
            domain=data.get("domain") or None,
            branding=self.build_branding(),
            capabilities=data.get("capabilities") or {},
        )


class TenantUpdateForm(forms.ModelForm):
    """Edit the registry row of a client: name, status, brand and capabilities.

    ``slug`` is deliberately excluded: it is the PostgreSQL schema name, and
    renaming it is a schema operation (``schema_rename``), not a form field.
    """

    class Meta:
        model = models.Tenant
        fields: ClassVar[list[str]] = [
            "name",
            "kind",
            "is_active",
            "logo",
            "primary_color",
            "chart_primary",
            "chart_success",
            "chart_warning",
            "chart_danger",
            "chart_info",
            "chart_dark",
            "capabilities",
        ]
        widgets: ClassVar[dict[str, Any]] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "capabilities": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "primary_color": forms.TextInput(attrs=COLOR_WIDGET),
            "chart_primary": forms.TextInput(attrs=COLOR_WIDGET),
            "chart_success": forms.TextInput(attrs=COLOR_WIDGET),
            "chart_warning": forms.TextInput(attrs=COLOR_WIDGET),
            "chart_danger": forms.TextInput(attrs=COLOR_WIDGET),
            "chart_info": forms.TextInput(attrs=COLOR_WIDGET),
            "chart_dark": forms.TextInput(attrs=COLOR_WIDGET),
        }

    def clean_capabilities(self) -> dict:
        """Store an empty capabilities field as an empty mapping, not ``NULL``.

        Returns:
            The submitted overrides, or ``{}`` when the field is blank; the
            column is not nullable and the kind defaults apply when it is empty.
        """
        return self.cleaned_data.get("capabilities") or {}
