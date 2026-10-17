from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View

from apps.core import mixins as core_mixins
from apps.organizations import scoping
from apps.users import filtersets, forms, models


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "users/profile.html"
    paginate_by = 6

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Profile")
        context["back_url"] = reverse_lazy("apps.dashboard:index")

        return context


class SettingsView(SuccessMessageMixin, LoginRequiredMixin, View):
    template_name = "users/settings.html"
    success_message = _("Settings updated successfully")
    success_url = reverse_lazy("apps.users:settings")

    def get_context_data(self, **kwargs):
        user = self.request.user

        context = {
            "entity": _("Settings"),
            "back_url": reverse_lazy("apps.dashboard:index"),
            "user_form": forms.UserSettingsForm(instance=user),
        }

        if user.is_account:
            context["account_form"] = forms.AccountSettingsForm(instance=user.account)

        context.update(kwargs)
        return context

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        try:
            user = request.user

            user_form = forms.UserSettingsForm(
                request.POST, request.FILES, instance=user
            )
            if user_form.is_valid():
                user_form.save()

            if user.is_account:
                account_form = forms.AccountSettingsForm(
                    request.POST, request.FILES, instance=user.account
                )

                if account_form.is_valid():
                    account_form.save()

            avatar_file = request.FILES.get("avatar")
            remove_avatar = request.POST.get("avatar_remove") == "1"
            if avatar_file or remove_avatar:
                user.avatar = avatar_file if avatar_file else None
                user.save(update_fields=["avatar"])

            messages.success(request, self.success_message)
            return redirect(self.success_url)
        except Exception as e:  # noqa: BLE001
            messages.error(request, f"Error updating settings: {e!s}")

        return render(request, self.template_name, self.get_context_data())


class AccountListView(core_mixins.BaseListView):
    model = models.Account
    permission_required = "users.view_account"
    filterset_class = filtersets.AccountFilter
    template_name = "users/account/list.html"
    context_object_name = "accounts"
    tenant_field = "user__organization"

    def get_queryset(self):
        """Return accounts with the user and organization preloaded."""
        return super().get_queryset().select_related("user", "user__organization")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Account")
        context["entity_plural"] = _("Accounts")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.users:account_create")

        return context


class AccountCreateView(core_mixins.BaseCreateView):
    form_class = forms.AccountCreationForm
    permission_required = "users.add_account"
    template_name = "users/account/form.html"
    success_message = _("Account created successfully")
    success_url = reverse_lazy("apps.users:account_list")

    def form_valid(self, form):
        form.save(self.request)
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop("instance", None)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Account")
        context["back_url"] = reverse_lazy("apps.users:account_list")
        return context


class AccountUpdateView(core_mixins.BaseUpdateView):
    model = models.Account
    context_object_name = "account"
    form_class = forms.AccountUpdateForm
    template_name = "users/account/form.html"
    permission_required = "users.change_account"
    success_message = _("Account updated successfully")
    success_url = reverse_lazy("apps.users:account_list")
    tenant_field = "user__organization"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Account")
        context["back_url"] = reverse_lazy("apps.users:account_list")
        return context


class AccountDeleteView(core_mixins.BaseDeleteView):
    model = models.Account
    permission_required = "users.delete_account"
    tenant_field = "user__organization"


class RoleListView(core_mixins.BaseListView):
    """List the roles visible to the acting user."""

    model = models.Role
    permission_required = "users.view_role"
    filterset_class = filtersets.RoleFilter
    template_name = "users/role/list.html"
    context_object_name = "roles"
    tenant_field = "organization"

    def get_queryset(self):
        """Return roles with organization, group and permission count."""
        return (
            super()
            .get_queryset()
            .select_related("organization", "group")
            .annotate(permission_count=Count("group__permissions"))
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Role")
        context["entity_plural"] = _("Roles")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.users:role_create")
        context["show_organization"] = scoping.can_choose_organization(
            self.request.user
        )
        return context


class RoleCreateView(core_mixins.BaseCreateView):
    """Create a role with its permission set."""

    model = models.Role
    form_class = forms.RoleForm
    permission_required = "users.add_role"
    template_name = "users/role/form.html"
    success_message = _("Role created successfully")
    success_url = reverse_lazy("apps.users:role_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Role")
        context["back_url"] = reverse_lazy("apps.users:role_list")
        return context


class RoleUpdateView(core_mixins.BaseUpdateView):
    """Update a role and its permission set."""

    model = models.Role
    form_class = forms.RoleForm
    permission_required = "users.change_role"
    template_name = "users/role/form.html"
    success_message = _("Role updated successfully")
    success_url = reverse_lazy("apps.users:role_list")
    context_object_name = "role"
    tenant_field = "organization"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Role")
        context["back_url"] = reverse_lazy("apps.users:role_list")
        return context


class RoleDeleteView(core_mixins.BaseDeleteView):
    """Delete a role (its backing group is removed by a signal)."""

    model = models.Role
    permission_required = "users.delete_role"
    tenant_field = "organization"


class UserListView(core_mixins.ClientAttributionMixin, core_mixins.BaseListView):
    """List the users visible to the acting user."""

    model = models.User
    permission_required = "users.view_user"
    filterset_class = filtersets.UserFilter
    template_name = "users/user/list.html"
    context_object_name = "users"

    def get_queryset(self):
        """Return users with organization and roles preloaded."""
        return (
            super()
            .get_queryset()
            .select_related("organization")
            .prefetch_related("groups__role")
            .order_by("first_name", "last_name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("User")
        context["entity_plural"] = _("Users")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.users:user_create")
        return context


class UserCreateView(core_mixins.BaseCreateView):
    """Create a user and assign their organization and roles."""

    model = models.User
    form_class = forms.UserManagementForm
    permission_required = "users.add_user"
    template_name = "users/user/form.html"
    success_message = _("User created successfully")
    success_url = reverse_lazy("apps.users:user_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["organization"] = self.request.GET.get("organization")
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("User")
        context["back_url"] = reverse_lazy("apps.users:user_list")
        return context


class UserUpdateView(core_mixins.BaseUpdateView):
    """Update a user's data, organization, status and roles."""

    model = models.User
    form_class = forms.UserManagementForm
    permission_required = "users.change_user"
    template_name = "users/user/form.html"
    success_message = _("User updated successfully")
    success_url = reverse_lazy("apps.users:user_list")
    context_object_name = "user"
    tenant_field = "organization"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["organization"] = self.request.GET.get("organization")
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("User")
        context["back_url"] = reverse_lazy("apps.users:user_list")
        return context


class UserDeleteView(core_mixins.BaseDeleteView):
    """Deactivate a user instead of deleting it."""

    model = models.User
    permission_required = "users.delete_user"
    tenant_field = "organization"

    def post(self, request, *args, **kwargs) -> JsonResponse:
        """Deactivate the user so soft-delete semantics are preserved."""
        user = (
            scoping.scope_queryset(
                models.User.objects.all(), request.user, field="organization"
            )
            .filter(pk=kwargs.get("pk"))
            .first()
        )
        if user is None:
            return JsonResponse(
                {"status": "error", "message": _("User not found.")}, status=404
            )
        user.is_active = False
        user.save(update_fields=["is_active"])
        return JsonResponse(
            {
                "status": "success",
                "message": _("The user was successfully deactivated."),
            }
        )
