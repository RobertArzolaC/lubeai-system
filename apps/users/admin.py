from typing import ClassVar

from allauth.account.models import EmailAddress
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.organizations import scoping
from apps.users import models
from apps.users.forms import CustomUserChangeForm, CustomUserCreationForm


class OrganizationListFilter(admin.SimpleListFilter):
    """Filter the user changelist by an organization in the actor's subtree."""

    title = _("Organization")
    parameter_name = "organization"

    def lookups(self, request: HttpRequest, model_admin) -> list[tuple[int, str]]:
        """Return the organizations the acting user may see."""
        return [
            (organization.pk, str(organization))
            for organization in scoping.visible_organizations(
                scoping.request_user(request)
            )
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        """Restrict the changelist to the selected organization."""
        if self.value():
            return queryset.filter(organization_id=self.value())
        return queryset


class _PreserveOrganizationMixin:
    """Keep the current organization when the admin field is left blank.

    A user without an organization is unrestricted in ``scoping``, so clearing
    the field by accident would silently widen that user's access. An empty
    selection therefore means "no change", mirroring the convention used by
    :class:`apps.core.mixins.forms.OrganizationScopeFormMixin`.
    """

    def clean_organization(self):
        """Treat an empty selection as "no change" for an existing user."""
        organization = self.cleaned_data.get("organization")
        if organization is None and self.instance.pk:
            return self.instance.organization
        return organization


@admin.register(models.User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = models.User
    list_display = (
        "email",
        "first_name",
        "last_name",
        "organization",
        "is_superuser",
        "is_staff",
        "is_active",
        "is_email_verified",
    )
    list_filter = (
        "is_active",
        "is_staff",
        OrganizationListFilter,
    )
    list_select_related = ("organization",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "avatar")},
        ),
        (
            "Organization",
            {"fields": ("organization",)},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_superuser",
                    "is_staff",
                    "is_active",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                    "organization",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
    )
    search_fields = ("email",)
    ordering = ("email",)

    def get_form(self, request, obj=None, **kwargs):
        """Bind the "empty means unchanged" rule to the organization field."""
        form_class = super().get_form(request, obj, **kwargs)
        return type(
            form_class.__name__,
            (_PreserveOrganizationMixin, form_class),
            {},
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs) -> forms.Field:
        """Scope the organization field to the actor's subtree.

        Actors that can only act on a single organization cannot reassign it,
        so their field is disabled instead of merely scoped.
        """
        if db_field.name == "organization":
            user = scoping.request_user(request)
            if scoping.can_choose_organization(user):
                kwargs.setdefault("queryset", scoping.visible_organizations(user))
            else:
                kwargs.setdefault("disabled", True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_list_filter(self, request) -> tuple:
        """Hide the organization filter from actors that cannot choose one."""
        filters = tuple(super().get_list_filter(request))
        if scoping.can_choose_organization(scoping.request_user(request)):
            return filters
        return tuple(f for f in filters if f is not OrganizationListFilter)

    def is_email_verified(self, obj):
        email = EmailAddress.objects.filter(user=obj, primary=True).first()
        return email.verified if email else False

    is_email_verified.short_description = "Verified"
    is_email_verified.boolean = True

    def get_queryset(self, request):
        self.request = request
        return super().get_queryset(request)


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "full_name",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
    )
    autocomplete_fields: ClassVar[list[str]] = ["user"]
    exclude = ("is_removed",)
