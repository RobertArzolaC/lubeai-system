from itertools import groupby
from typing import ClassVar

from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Permission
from django.utils.translation import gettext_lazy as _

from apps.core import mixins as core_mixins
from apps.organizations import scoping
from apps.users import models, services


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = models.User
        fields = ("email",)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = models.User
        fields = ("email",)


class UserSettingsForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, label=_("First name"))
    last_name = forms.CharField(max_length=30, label=_("Last name"), required=False)

    class Meta:
        model = models.User
        fields: ClassVar[list[str]] = ["first_name", "last_name"]


class RoleForm(core_mixins.OrganizationScopeFormMixin, forms.ModelForm):
    """Create or update a tenant-scoped role and its permission set.

    The form exposes a ``permissions`` multiple choice rendered as a matrix
    grouped by model (see :attr:`permission_groups`). Saving delegates to
    :class:`apps.users.services.RoleService` so the backing Django group stays
    in sync (name and permissions).
    """

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model", "codename"
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Permissions"),
    )

    class Meta:
        model = models.Role
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
        """Scope the organization field to the acting user.

        The owning organization is immutable on update: a role must never be
        silently moved across tenants.
        """
        super().__init__(*args, user=user, **kwargs)
        if self.instance.pk and "organization" in self.fields:
            self.fields["organization"].disabled = True

    @property
    def selected_permission_ids(self) -> set[str]:
        """Return the ids of the currently selected permissions as strings."""
        if self.is_bound:
            values = (
                self.data.getlist("permissions")
                if hasattr(self.data, "getlist")
                else []
            )
            return {str(value) for value in values}
        if self.instance.pk and self.instance.group_id:
            return {
                str(pk)
                for pk in self.instance.group.permissions.values_list("pk", flat=True)
            }
        return set()

    @property
    def permission_groups(self) -> list[dict]:
        """Return the permissions grouped by model for the matrix template."""
        queryset = self.fields["permissions"].queryset

        def key(permission: Permission) -> tuple[str, str]:
            """Group permissions by their content type."""
            return (
                permission.content_type.app_label,
                permission.content_type.model,
            )

        groups: list[dict] = []
        for (_app_label, _model), items in groupby(queryset, key=key):
            permissions = list(items)
            content_type = permissions[0].content_type
            groups.append(
                {
                    "key": f"{content_type.app_label}.{content_type.model}",
                    "label": content_type.name.capitalize(),
                    "app_label": content_type.app_label,
                    "permissions": permissions,
                }
            )
        return groups

    def _resolve_organization(self) -> object:
        """Return the selected organization or fall back to the actor's own."""
        return (
            self.cleaned_data.get("organization")
            or getattr(self.instance, "organization", None)
            or getattr(self.user, "organization", None)
        )

    def save(self, commit: bool = True) -> models.Role:
        """Persist the role through :class:`RoleService`."""
        service = services.RoleService()
        permissions = self.cleaned_data.get("permissions", [])
        if self.instance.pk:
            self.instance = service.update_role(
                self.instance,
                name=self.cleaned_data["name"],
                description=self.cleaned_data.get("description", ""),
                is_active=self.cleaned_data.get("is_active", True),
                permissions=permissions,
                actor=self.user,
            )
        else:
            self.instance = service.create_role(
                organization=self._resolve_organization(),
                name=self.cleaned_data["name"],
                description=self.cleaned_data.get("description", ""),
                permissions=permissions,
                actor=self.user,
            )
        return self.instance


class UserManagementForm(core_mixins.OrganizationScopeFormMixin, forms.ModelForm):
    """Create or update a user of an organization, with role assignment.

    The ``organization`` field is scoped to the acting user's subtree (via
    :class:`~apps.core.mixins.forms.OrganizationScopeFormMixin`) and ``roles``
    offers only the active roles within that subtree. Saving delegates to
    :class:`apps.users.services.UserService`.
    """

    roles = forms.ModelMultipleChoiceField(
        queryset=models.Role.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Roles"),
    )

    class Meta:
        model = models.User
        fields: ClassVar[list[str]] = [
            "organization",
            "first_name",
            "last_name",
            "email",
            "is_active",
        ]
        widgets: ClassVar[dict] = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(
        self,
        *args,
        organization=None,
        user=None,
        **kwargs,
    ) -> None:
        """Scope organization/roles and preload the instance's roles.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            organization: Optional organization id to preselect.
            user: The acting user, used to scope the choices.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, user=user, **kwargs)
        self._preset_organization = organization

        if organization is not None and "organization" in self.fields:
            self.fields["organization"].initial = organization

        role_queryset = models.Role.objects.filter(is_active=True).select_related(
            "organization"
        )
        if user is not None:
            visible_ids = scoping.user_visible_organization_ids(user)
            if visible_ids is not None:
                role_queryset = role_queryset.filter(organization_id__in=visible_ids)
        self.fields["roles"].queryset = role_queryset

        if self.instance.pk:
            self.fields["email"].disabled = True
            self.fields["roles"].initial = [
                group.role
                for group in self.instance.groups.all()
                if hasattr(group, "role")
            ]

    def clean_email(self) -> str:
        """Reject a duplicate email case-insensitively (avoids a 500)."""
        email = self.cleaned_data.get("email")
        if (
            email
            and not self.instance.pk
            and models.User.objects.filter(email__iexact=email).exists()
        ):
            raise forms.ValidationError(
                _("A user with this email already exists."), code="duplicate"
            )
        return email

    def clean(self) -> dict:
        """Reject roles that do not belong to the selected organization."""
        cleaned = super().clean()
        organization = cleaned.get("organization") or getattr(
            self.instance, "organization", None
        )
        roles = cleaned.get("roles")
        if organization is not None and roles:
            mismatched = bool(
                [role for role in roles if role.organization_id != organization.pk]
            )
            if mismatched:
                self.add_error(
                    "roles",
                    _("One or more roles do not belong to the selected organization."),
                )
        return cleaned

    def save(self, commit: bool = True) -> models.User:
        """Persist the user through :class:`UserService`.

        Args:
            commit: Accepted for signature compatibility (unused).

        Returns:
            The created or updated user.
        """
        service = services.UserService()
        roles = self.cleaned_data.get("roles", [])
        organization = self.cleaned_data.get("organization") or getattr(
            self.instance, "organization", None
        )
        if self.instance.pk:
            self.instance = service.update_user(
                self.instance,
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                organization=organization,
                roles=roles,
                is_active=self.cleaned_data.get("is_active", True),
            )
        else:
            self.instance = service.create_user(
                actor=self.user,
                email=self.cleaned_data["email"],
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                organization=organization,
                roles=roles,
                is_active=self.cleaned_data.get("is_active", True),
            )
        return self.instance
