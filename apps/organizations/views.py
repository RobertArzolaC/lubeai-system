"""Views for the organizations app."""

from __future__ import annotations

from typing import Any

from django.db.models import Count, QuerySet
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.core import mixins as core_mixins
from apps.organizations import filtersets, forms, models, scoping


class OrganizationListView(core_mixins.BaseListView):
    """List the organizations visible to the acting user."""

    model = models.Organization
    permission_required = "organizations.view_organization"
    filterset_class = filtersets.OrganizationFilter
    template_name = "organizations/organization/list.html"
    context_object_name = "organizations"

    def get_queryset(self) -> QuerySet:
        """Return the visible subtree with parent and child count preloaded."""
        return (
            scoping.visible_organizations(self.request.user)
            .select_related("parent")
            .annotate(children_count=Count("children"))
            .order_by("name")
        )

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Organization")
        context["entity_plural"] = _("Organizations")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy(
            "apps.organizations:organization_create"
        )
        return context


class OrganizationCreateView(core_mixins.BaseCreateView):
    """Create an organization within the acting user's subtree."""

    model = models.Organization
    form_class = forms.OrganizationForm
    permission_required = "organizations.add_organization"
    template_name = "organizations/organization/form.html"
    success_message = _("Organization created successfully")
    success_url = reverse_lazy("apps.organizations:organization_list")

    def get_form_kwargs(self) -> dict:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Organization")
        context["back_url"] = reverse_lazy("apps.organizations:organization_list")
        return context


class OrganizationUpdateView(core_mixins.BaseUpdateView):
    """Update an organization within the acting user's subtree."""

    model = models.Organization
    form_class = forms.OrganizationForm
    permission_required = "organizations.change_organization"
    template_name = "organizations/organization/form.html"
    success_message = _("Organization updated successfully")
    success_url = reverse_lazy("apps.organizations:organization_list")
    context_object_name = "organization"

    def get_queryset(self) -> QuerySet:
        """Scope updatable organizations to the user's subtree."""
        return scoping.visible_organizations(self.request.user)

    def get_form_kwargs(self) -> dict:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Organization")
        context["back_url"] = reverse_lazy("apps.organizations:organization_list")
        return context


class OrganizationDeleteView(core_mixins.BaseDeleteView):
    """Delete a leaf organization with no child organizations or users."""

    model = models.Organization
    permission_required = "organizations.delete_organization"

    def post(self, request, *args: Any, **kwargs: Any) -> JsonResponse:
        """Delete the organization unless it still has children or users."""
        organization = (
            scoping.visible_organizations(request.user)
            .filter(pk=kwargs.get("pk"))
            .first()
        )
        if organization is None:
            return JsonResponse(
                {"status": "error", "message": _("Organization not found.")},
                status=404,
            )
        if organization.children.exists() or organization.users.exists():
            return JsonResponse(
                {
                    "status": "error",
                    "message": _(
                        "This organization still has child organizations or users."
                    ),
                },
                status=400,
            )
        organization.delete()
        return JsonResponse(
            {
                "status": "success",
                "message": _("The organization was successfully deleted."),
            }
        )
