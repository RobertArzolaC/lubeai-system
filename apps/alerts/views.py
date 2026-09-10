from typing import Any

from django.db.models import Count, Q, QuerySet
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.alerts import choices, filtersets, forms, models
from apps.core import mixins as core_mixins


class AlertListView(core_mixins.BaseListView):
    """List view for the Alert model."""

    model = models.Alert
    permission_required = "alerts.view_alert"
    filterset_class = filtersets.AlertFilter
    template_name = "alerts/alert/list.html"
    context_object_name = "alerts"

    def get_queryset(self) -> QuerySet:
        """Return alerts with related objects to avoid N+1 queries."""
        return models.Alert.objects.select_related(
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
        context["status_counts"] = models.Alert.objects.aggregate(
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
        return models.Alert.objects.select_related(
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
