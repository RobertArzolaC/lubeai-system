import mimetypes
from pathlib import Path
from typing import Any

from django.core.exceptions import SuspiciousFileOperation
from django.db.models import Count, Q, QuerySet
from django.http import FileResponse, Http404, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.text import get_valid_filename
from django.utils.translation import gettext_lazy as _

from apps.alerts import choices, filtersets, forms, models
from apps.alerts.services.alert_service import AlertService
from apps.core import mixins as core_mixins
from apps.organizations import scoping


class AlertListView(core_mixins.ClientAttributionMixin, core_mixins.BaseListView):
    """List view for the Alert model."""

    model = models.Alert
    permission_required = "alerts.view_alert"
    filterset_class = filtersets.AlertFilter
    template_name = "alerts/alert/list.html"
    context_object_name = "alerts"

    def get_queryset(self) -> QuerySet:
        """Return alerts with related objects to avoid N+1 queries."""
        return super().get_queryset().select_related(
            "machine",
            "component",
            "component__type",
            "component__machine",
            "report",
        )

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity names, navigation URLs and status summary counts."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Alert")
        context["entity_plural"] = _("Alerts")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["status_choices"] = choices.AlertStatus.choices
        context["status_counts"] = self.get_queryset().aggregate(
            total=Count("id"),
            open=Count("id", filter=Q(status=choices.AlertStatus.OPEN)),
            acknowledged=Count("id", filter=Q(status=choices.AlertStatus.ACKNOWLEDGED)),
            resolved=Count("id", filter=Q(status=choices.AlertStatus.RESOLVED)),
            critical=Count("id", filter=Q(severity=choices.AlertSeverity.CRITICAL)),
        )
        return context


class AlertDetailView(core_mixins.BaseDetailView):
    """Detail view for the Alert model."""

    model = models.Alert
    permission_required = "alerts.view_alert"
    template_name = "alerts/alert/detail.html"
    context_object_name = "alert"

    def get_queryset(self) -> QuerySet:
        """Optimize the query with the related objects used by the template."""
        return super().get_queryset().select_related(
            "machine",
            "component",
            "component__type",
            "component__machine",
            "report",
            "report__laboratory",
            "acknowledged_by",
        )

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URLs."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Alert")
        context["back_url"] = reverse_lazy("apps.alerts:alert_list")
        context["edit_url"] = reverse_lazy(
            "apps.alerts:alert_update", kwargs={"pk": self.object.pk}
        )
        return context


class AlertUpdateView(core_mixins.BaseUpdateView):
    """Update view for the Alert model."""

    model = models.Alert
    form_class = forms.AlertForm
    permission_required = "alerts.change_alert"
    template_name = "alerts/alert/form.html"
    success_message = _("Alert updated successfully")
    success_url = reverse_lazy("apps.alerts:alert_list")
    context_object_name = "alert"

    def get_form_kwargs(self) -> dict:
        """Pass the acting user to the form for lifecycle stamping."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URL."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Alert")
        context["back_url"] = reverse_lazy("apps.alerts:alert_list")
        return context


class AlertDeleteView(core_mixins.BaseDeleteView):
    """Delete view for the Alert model using AJAX."""

    model = models.Alert
    permission_required = "alerts.delete_alert"


class AlertStatusUpdateView(core_mixins.BaseView):
    """Update the lifecycle status of an alert from the status modal.

    Acknowledging or resolving an alert is the operation users perform from the
    list, so it is a small AJAX endpoint instead of a full form round-trip. The
    submitted ``status``, description and optional attachment are applied
    through :class:`~apps.alerts.services.alert_service.AlertService`, which
    keeps the lifecycle stamps and the history entry in sync.
    """

    model = models.Alert
    permission_required = "alerts.change_alert"

    def handle_no_permission(self) -> HttpResponseBase:
        """Redirect anonymous users, answer a JSON 403 to the others.

        The modal calls this endpoint with ``fetch``, so an authenticated user
        without ``alerts.change_alert`` must get a JSON body instead of the
        HTML error page Django renders by default.
        """
        if self.request.user.is_authenticated:
            return JsonResponse(
                {
                    "status": "error",
                    "message": _("You do not have permission to change this alert."),
                },
                status=403,
            )
        return super().handle_no_permission()

    def post(self, request, *args: Any, **kwargs: Any) -> JsonResponse:
        """Apply the submitted status to the alert and answer as JSON.

        Args:
            request: The current POST request; ``status``, ``note`` and
                ``attachment`` carry the new value and its optional context.
            *args: Unused positional arguments.
            **kwargs: URL keyword arguments; ``pk`` identifies the alert.

        Returns:
            A JSON payload with the new status and its history entry, or an
            error payload with the matching HTTP status: 400 for an invalid
            value, 404 when the alert is not reachable (including another
            organization's alert) and 403 when the user lacks
            ``alerts.change_alert``.
        """
        form = forms.AlertStatusForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse(
                {
                    "status": "error",
                    "message": _("Invalid status."),
                    "errors": form.errors,
                },
                status=400,
            )

        try:
            alert = core_mixins.scope_view_queryset(
                self, self.model._default_manager.all()
            ).get(pk=kwargs.get("pk"))
        except self.model.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": _("Alert not found.")},
                status=404,
            )

        history = AlertService().change_status(
            alert,
            status=form.cleaned_data["status"],
            user=request.user,
            note=form.cleaned_data["note"],
            attachment=form.cleaned_data["attachment"],
        )
        attachment_url = None
        if history.attachment:
            attachment_url = reverse(
                "apps.alerts:alert_attachment_download",
                kwargs={"pk": history.pk},
            )
        return JsonResponse(
            {
                "status": "success",
                "message": _("Alert status updated."),
                "new_status": alert.status,
                "new_status_display": alert.get_status_display(),
                "history_id": history.pk,
                "attachment_url": attachment_url,
            }
        )


class AlertAttachmentDownloadView(core_mixins.BaseView):
    """Stream a status attachment to users allowed to view the alert."""

    permission_required = "alerts.view_alert"

    def get(self, request, *args: Any, **kwargs: Any) -> FileResponse:
        """Return the stored attachment, scoped to the user's organizations.

        Args:
            request: The current HTTP request.
            *args: Unused positional arguments.
            **kwargs: URL keyword arguments; ``pk`` identifies the history entry.

        Returns:
            The attachment as a download.

        Raises:
            Http404: If the entry is not reachable, has no attachment or the
                stored file is missing.
        """
        history = get_object_or_404(
            scoping.scope_queryset(
                models.AlertStatusHistory.objects.select_related("alert"),
                request.user,
                field="alert__organization",
            ),
            pk=kwargs["pk"],
        )
        if not history.attachment:
            raise Http404
        try:
            file_handle = history.attachment.open("rb")
        except OSError as exc:
            raise Http404 from exc

        original_name = Path(history.attachment.name).name
        try:
            filename = get_valid_filename(original_name)
        except SuspiciousFileOperation:
            filename = "attachment"

        content_type = (
            mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        )
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=filename,
            content_type=content_type,
        )
        response["Cache-Control"] = "private, no-store"
        return response
