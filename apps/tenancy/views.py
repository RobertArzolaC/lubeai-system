"""Views for the platform's tenant console.

Ruling: the console is served from the operations tenant and registered in the
tenant urlconf (``config.urls``), not in a SHARED one. ``auth``, ``admin`` and
``sessions`` are TENANT apps, so a SHARED module could not log a user in;
``config.urls_public`` (the ``public`` schema) deliberately has no session and
therefore never exposes the console. Every view here answers 404 outside the
operations tenant and is additionally protected by a ``tenancy`` permission.
"""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import connection
from django.db.models import QuerySet
from django.http import Http404, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.core import mixins as core_mixins
from apps.tenancy import constants, filtersets, forms, models, services


class OpsTenantRequiredMixin:
    """Restrict a view to the platform's operations tenant.

    The tenant urlconf makes these routes resolvable from any client, so each
    view checks the request tenant first: only ``ops`` owns the registry.
    """

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponseBase:
        """Answer 404 unless the request is served by the operations tenant.

        Args:
            request: The current HTTP request. ``request.tenant`` is set by
                ``TenantMainMiddleware``.
            *args: Positional arguments for the wrapped view.
            **kwargs: Keyword arguments for the wrapped view.

        Raises:
            Http404: When the request tenant is missing or is not ``ops``.
        """
        tenant = getattr(request, "tenant", None)
        if tenant is None or not getattr(tenant, "is_ops", False):
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class TenantListView(OpsTenantRequiredMixin, core_mixins.BaseListView):
    """List every client tenant of the platform."""

    model = models.Tenant
    permission_required = "tenancy.view_tenant"
    filterset_class = filtersets.TenantFilter
    template_name = "tenancy/tenant/list.html"
    context_object_name = "tenants"

    def get_queryset(self) -> QuerySet:
        """Return the registry ordered by name with domains preloaded."""
        return models.Tenant.objects.prefetch_related("domains").order_by("name")

    def get_context_data(self, **kwargs: Any) -> dict:
        """Expose the entity labels and navigation targets to the template."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Tenant")
        context["entity_plural"] = _("Tenants")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.tenancy:tenant_create")
        return context


class TenantDetailView(OpsTenantRequiredMixin, core_mixins.BaseDetailView):
    """Show a tenant with its domains, brand, capabilities and consumption."""

    model = models.Tenant
    permission_required = "tenancy.view_tenant"
    template_name = "tenancy/tenant/detail.html"
    context_object_name = "tenant"

    def get_queryset(self) -> QuerySet:
        """Return the registry with domains preloaded."""
        return models.Tenant.objects.prefetch_related("domains")

    def get_context_data(self, **kwargs: Any) -> dict:
        """Measure the tenant's usage and expose its domains."""
        context = super().get_context_data(**kwargs)
        context["consumption"] = services.TenantService.consumption(self.object)
        context["tenant_branding"] = {
            slot: getattr(self.object, slot, "") or ""
            for slot in constants.BRANDING_SLOTS
        }
        context["back_url"] = reverse_lazy("apps.tenancy:tenant_list")
        return context


class TenantCreateView(
    OpsTenantRequiredMixin, SuccessMessageMixin, core_mixins.BaseFormView
):
    """Provision a new client tenant."""

    form_class = forms.TenantProvisionForm
    permission_required = "tenancy.add_tenant"
    template_name = "tenancy/tenant/form.html"
    success_url = reverse_lazy("apps.tenancy:tenant_list")
    success_message = _("Tenant created successfully")

    def form_valid(self, form: forms.TenantProvisionForm) -> HttpResponseBase:
        """Provision the tenant, surfacing provisioning errors on the form.

        Args:
            form: The validated provisioning form.

        Returns:
            A redirect to the registry on success, or the invalid form when
            provisioning raised a ``ValueError`` (e.g. a domain race).
        """
        try:
            form.save()
        except ValueError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict:
        """Expose the entity label, the back link and the form action."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Tenant")
        context["back_url"] = reverse_lazy("apps.tenancy:tenant_list")
        context["form_action"] = reverse_lazy("apps.tenancy:tenant_create")
        return context


class TenantUpdateView(OpsTenantRequiredMixin, core_mixins.BaseUpdateView):
    """Edit a tenant's name, status, brand and capabilities."""

    model = models.Tenant
    form_class = forms.TenantUpdateForm
    permission_required = "tenancy.change_tenant"
    template_name = "tenancy/tenant/form.html"
    success_message = _("Tenant updated successfully")
    success_url = reverse_lazy("apps.tenancy:tenant_list")
    context_object_name = "tenant"

    def form_valid(self, form: forms.TenantUpdateForm) -> HttpResponseBase:
        """Save the registry row while the connection is on ``public``.

        ``TenantMixin.save`` refuses to update a tenant outside its own schema
        or ``public``; the console runs inside the operations tenant, so the
        connection is switched for the write and restored afterwards.

        Args:
            form: The validated update form.

        Returns:
            The redirect produced by the generic update view.
        """
        previous_tenant = connection.tenant
        connection.set_schema_to_public()
        try:
            return super().form_valid(form)
        finally:
            connection.set_tenant(previous_tenant)

    def get_context_data(self, **kwargs: Any) -> dict:
        """Expose the entity label, the back link and the form action."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Tenant")
        context["back_url"] = reverse_lazy("apps.tenancy:tenant_list")
        context["form_action"] = reverse_lazy(
            "apps.tenancy:tenant_update", kwargs={"pk": self.object.pk}
        )
        return context


class TenantToggleActiveView(OpsTenantRequiredMixin, core_mixins.BaseView):
    """Suspend or reactivate a tenant."""

    permission_required = "tenancy.change_tenant"

    def post(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponseBase:
        """Toggle ``is_active`` and redirect back to the registry.

        Args:
            request: The current HTTP request.
            *args: Unused positional arguments.
            **kwargs: Routing kwargs; ``pk`` identifies the tenant.

        Returns:
            A redirect to the tenant list.
        """
        tenant = get_object_or_404(models.Tenant, pk=kwargs["pk"])
        services.TenantService.set_active(tenant, not tenant.is_active)
        if tenant.is_active:
            messages.success(request, _("Tenant activated."))
        else:
            messages.success(request, _("Tenant suspended."))
        return redirect("apps.tenancy:tenant_list")
