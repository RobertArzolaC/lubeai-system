from typing import Any, ClassVar

from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django_filters.views import FilterView

from apps.core import mixins as core_mixins


class BaseCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SuccessMessageMixin,
    core_mixins.UserStampMixin,
    CreateView,
):
    pass


class BaseUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SuccessMessageMixin,
    core_mixins.UserStampMixin,
    UpdateView,
):
    pass


class BaseListView(LoginRequiredMixin, PermissionRequiredMixin, FilterView, ListView):
    """List view with reusable ``items_per_page`` pagination handling.

    Subclasses may override ``paginate_by`` to change the default page size;
    ``page_size_options`` defines the values accepted from the query string.
    """

    page_size_options: ClassVar[tuple[int, ...]] = (5, 10, 25, 50)
    default_page_size: ClassVar[int] = 5
    paginate_by: int | None = 5

    def get_paginate_by(self, queryset) -> int:
        """Return the page size from ``items_per_page`` or the view default.

        Args:
            queryset: The queryset being paginated (unused).

        Returns:
            A page size from ``page_size_options`` when the query parameter is
            valid, otherwise ``paginate_by`` or ``default_page_size``.
        """
        requested = self.request.GET.get("items_per_page")
        if requested is not None:
            try:
                size = int(requested)
            except (TypeError, ValueError):
                size = None
            if size in self.page_size_options:
                return size
        return self.paginate_by or self.default_page_size

    def get_context_data(self, **kwargs: Any) -> dict:
        """Expose the allowed page sizes to the pagination template."""
        context = super().get_context_data(**kwargs)
        context["page_size_options"] = self.page_size_options
        return context


class BaseTemplateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    pass


class BaseDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    pass


class BaseFormView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    pass


class BaseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        object_id = kwargs.get("pk")
        entity_name = self.model._meta.verbose_name
        try:
            current_object = self.model.objects.get(pk=object_id)
            current_object.delete()
            return JsonResponse(
                {
                    "status": "success",
                    "message": _("The %(entity_name)s was successfully deleted.")
                    % {"entity_name": entity_name},
                }
            )
        except self.model.DoesNotExist:
            return JsonResponse(
                {
                    "status": "error",
                    "message": _("%(entity_name)s not found.")
                    % {"entity_name": entity_name},
                },
                status=404,
            )
        except Exception as e:  # noqa: BLE001
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    def handle_no_permission(self):
        return JsonResponse(
            {
                "status": "error",
                "message": _("You do not have permission to delete this account."),
            },
            status=403,
        )
