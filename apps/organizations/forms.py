"""Forms for the organizations app."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.organizations import choices, models, scoping
from apps.organizations.services import OrganizationService

if TYPE_CHECKING:
    from apps.users.models import User


class OrganizationForm(forms.ModelForm):
    """Create or update an organization within the acting user's subtree.

    The ``parent`` field is scoped to the organizations the acting user may see,
    the ``kind`` field cannot be set to ``PLATFORM`` by non-superusers, and the
    slug is derived from the name when left blank.
    """

    class Meta:
        model = models.Organization
        fields: ClassVar[list[str]] = [
            "name",
            "code",
            "kind",
            "parent",
            "phone",
            "email",
            "description",
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
        widgets: ClassVar[dict] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "capabilities": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, user: User | None = None, **kwargs) -> None:
        """Scope the parent choices to the acting user's subtree.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            user: The acting user, used to scope the parent choices.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, **kwargs)
        self.user = user
        parent_field = self.fields.get("parent")
        if parent_field is None:
            return
        parent_field.required = False
        if user is None:
            return
        queryset = scoping.visible_organizations(user)
        if self.instance.pk is not None:
            queryset = queryset.exclude(
                pk__in=self.instance.descendants(include_self=True)
            )
        parent_field.queryset = queryset

    def clean_parent(self):
        """Reject parents outside the subtree or that would create a cycle."""
        parent = self.cleaned_data.get("parent")
        if parent is None:
            return parent
        if self.user is not None and not scoping.is_organization_visible(
            self.user, parent
        ):
            raise ValidationError(_("You cannot use that parent."), code="invalid")
        OrganizationService.assert_valid_parent(self.instance, parent)
        return parent

    def clean_kind(self):
        """Only superusers may create platform organizations."""
        kind = self.cleaned_data.get("kind")
        if kind == choices.OrganizationKind.PLATFORM and not getattr(
            self.user, "is_superuser", False
        ):
            raise ValidationError(_("You cannot create a platform."), code="invalid")
        return kind

    def save(self, commit: bool = True) -> models.Organization:
        """Persist the organization, generating a slug when left blank."""
        organization = super().save(commit=False)
        if not organization.slug:
            organization.slug = OrganizationService.ensure_unique_slug(
                organization.name, exclude_pk=organization.pk
            )
        if commit:
            organization.save()
            self.save_m2m()
        return organization
