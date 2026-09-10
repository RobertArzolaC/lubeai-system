from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q, QuerySet
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django_filters.views import FilterView

from apps.core import mixins as core_mixins
from apps.reports import constants, filtersets, forms, models
from apps.reports.services import ReportExportService

EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ============================================================================
# LABORATORY CRUD VIEWS
# ============================================================================


class LaboratoryListView(core_mixins.BaseListView):
    """List view for the Laboratory model."""

    model = models.Laboratory
    permission_required = "reports.view_laboratory"
    filterset_class = filtersets.LaboratoryFilter
    template_name = "reports/laboratory/list.html"
    context_object_name = "laboratories"
    paginate_by = 5

    def get_queryset(self) -> QuerySet:
        """Return laboratories annotated with their active report count."""
        return models.Laboratory.objects.annotate(
            reports_count=Count("reports", filter=Q(reports__is_active=True))
        ).order_by("name")

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity names and navigation URLs."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Laboratory")
        context["entity_plural"] = _("Laboratories")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.reports:laboratory_create")
        return context


class LaboratoryDetailView(core_mixins.BaseDetailView):
    """Detail view for the Laboratory model."""

    model = models.Laboratory
    permission_required = "reports.view_laboratory"
    template_name = "reports/laboratory/detail.html"
    context_object_name = "laboratory"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add related reports and navigation URLs."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Laboratory")
        context["back_url"] = reverse_lazy("apps.reports:laboratory_list")
        context["edit_url"] = reverse_lazy(
            "apps.reports:laboratory_update", kwargs={"pk": self.object.pk}
        )
        context["reports"] = self.object.reports.select_related(
            "machine", "component"
        ).filter(is_active=True)[:10]
        return context


class LaboratoryCreateView(core_mixins.BaseCreateView):
    """Create view for the Laboratory model."""

    model = models.Laboratory
    form_class = forms.LaboratoryForm
    permission_required = "reports.add_laboratory"
    template_name = "reports/laboratory/form.html"
    success_message = _("Laboratory created successfully")
    success_url = reverse_lazy("apps.reports:laboratory_list")

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URL."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Laboratory")
        context["back_url"] = reverse_lazy("apps.reports:laboratory_list")
        return context


class LaboratoryUpdateView(core_mixins.BaseUpdateView):
    """Update view for the Laboratory model."""

    model = models.Laboratory
    form_class = forms.LaboratoryForm
    permission_required = "reports.change_laboratory"
    template_name = "reports/laboratory/form.html"
    success_message = _("Laboratory updated successfully")
    success_url = reverse_lazy("apps.reports:laboratory_list")
    context_object_name = "laboratory"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URL."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Laboratory")
        context["back_url"] = reverse_lazy("apps.reports:laboratory_list")
        return context


class LaboratoryDeleteView(core_mixins.BaseDeleteView):
    """Delete view for the Laboratory model using AJAX."""

    model = models.Laboratory
    permission_required = "reports.delete_laboratory"


# ============================================================================
# REPORT CRUD VIEWS
# ============================================================================


class ReportListView(core_mixins.BaseListView):
    """List view for the Report model."""

    model = models.Report
    permission_required = "reports.view_report"
    filterset_class = filtersets.ReportFilter
    template_name = "reports/report/list.html"
    context_object_name = "reports"
    paginate_by = 5

    def get_queryset(self) -> QuerySet:
        """Return reports with related objects to avoid N+1 queries."""
        return models.Report.objects.select_related(
            "laboratory", "machine", "component"
        )

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity names and navigation URLs."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Report")
        context["entity_plural"] = _("Reports")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.reports:report_create")
        context["export_url"] = reverse_lazy("apps.reports:report_export")
        return context


class ReportDetailView(core_mixins.BaseDetailView):
    """Detail view for the Report model."""

    model = models.Report
    permission_required = "reports.view_report"
    template_name = "reports/report/detail.html"
    context_object_name = "report"

    def get_queryset(self) -> QuerySet:
        """Optimize query with select_related for related objects."""
        return models.Report.objects.select_related(
            "laboratory", "machine", "component", "component__type", "analysis"
        )

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add analysis and navigation URLs."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Report")
        context["back_url"] = reverse_lazy("apps.reports:report_list")
        context["edit_url"] = reverse_lazy(
            "apps.reports:report_update", kwargs={"pk": self.object.pk}
        )
        context["analysis"] = getattr(self.object, "analysis", None)
        return context


class ReportCreateView(core_mixins.BaseCreateView):
    """Create view for the Report model."""

    model = models.Report
    form_class = forms.ReportForm
    permission_required = "reports.add_report"
    template_name = "reports/report/form.html"
    success_message = _("Report created successfully")
    success_url = reverse_lazy("apps.reports:report_list")

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URL."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Report")
        context["back_url"] = reverse_lazy("apps.reports:report_list")
        context["form_title"] = _("Create Report")
        return context


class ReportUpdateView(core_mixins.BaseUpdateView):
    """Update view for the Report model."""

    model = models.Report
    form_class = forms.ReportForm
    permission_required = "reports.change_report"
    template_name = "reports/report/form.html"
    success_message = _("Report updated successfully")
    success_url = reverse_lazy("apps.reports:report_list")
    context_object_name = "report"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URL."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Report")
        context["back_url"] = reverse_lazy("apps.reports:report_list")
        context["form_title"] = _("Edit Report")
        return context


class ReportDeleteView(core_mixins.BaseDeleteView):
    """Delete view for the Report model using AJAX."""

    model = models.Report
    permission_required = "reports.delete_report"


# ============================================================================
# REPORT EXPORT VIEWS
# ============================================================================


class ReportExportQueryMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Shared filtering behaviour for the report export views."""

    permission_required = "reports.view_report"

    def get_filtered_queryset(self) -> QuerySet:
        """Return the report queryset filtered by request GET parameters."""
        queryset = models.Report.objects.select_related(
            "laboratory",
            "machine",
            "machine__branch",
            "component",
            "component__type",
            "analysis",
        )
        self.filterset = filtersets.ReportExportFilter(
            self.request.GET, queryset=queryset
        )
        return self.filterset.qs


class ReportExportPageView(LoginRequiredMixin, PermissionRequiredMixin, FilterView):
    """Render the report export form with live filters."""

    permission_required = "reports.view_report"
    filterset_class = filtersets.ReportExportFilter
    template_name = "reports/report/export.html"

    def get_queryset(self) -> QuerySet:
        """Return reports with related objects for the preview form."""
        return models.Report.objects.select_related(
            "laboratory", "machine", "component"
        )

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add navigation URLs and export limits."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Report Export")
        context["back_url"] = reverse_lazy("apps.reports:report_list")
        context["preview_url"] = reverse_lazy("apps.reports:report_export_preview")
        context["download_url"] = reverse_lazy("apps.reports:report_export_download")
        context["max_records"] = constants.MAX_EXPORT_RECORDS
        return context


class ReportExportPreviewAPIView(ReportExportQueryMixin, View):
    """Return a JSON preview of the reports that would be exported."""

    preview_limit = 20

    def get(self, request, *args, **kwargs) -> JsonResponse:
        """Return the preview columns, rows and total record count."""
        queryset = self.get_filtered_queryset()
        count = queryset.count()

        if count > constants.MAX_EXPORT_RECORDS:
            return JsonResponse(
                {
                    "status": "error",
                    "message": _(
                        "The result exceeds the maximum of %(max)s records. "
                        "Please refine your filters."
                    )
                    % {"max": constants.MAX_EXPORT_RECORDS},
                },
                status=400,
            )

        preview = ReportExportService.preview(queryset, limit=self.preview_limit)
        return JsonResponse(
            {
                "status": "success",
                "count": count,
                "columns": preview["columns"],
                "rows": preview["rows"],
            }
        )


class ReportExportDownloadView(ReportExportQueryMixin, View):
    """Stream the filtered reports as an Excel file."""

    def get(self, request, *args, **kwargs) -> HttpResponse | JsonResponse:
        """Return the generated Excel file or a JSON error when too large."""
        queryset = self.get_filtered_queryset()
        if queryset.count() > constants.MAX_EXPORT_RECORDS:
            return JsonResponse(
                {
                    "status": "error",
                    "message": _(
                        "The result exceeds the maximum of %(max)s records. "
                        "Please refine your filters."
                    )
                    % {"max": constants.MAX_EXPORT_RECORDS},
                },
                status=400,
            )

        buffer, filename = ReportExportService.export_to_response(queryset)
        response = HttpResponse(buffer.getvalue(), content_type=EXCEL_CONTENT_TYPE)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ============================================================================
# ANALYSIS THRESHOLD CRUD VIEWS
# ============================================================================


class AnalysisThresholdListView(core_mixins.BaseListView):
    """List view for AnalysisThreshold model."""

    model = models.AnalysisThreshold
    permission_required = "reports.view_analysisthreshold"
    filterset_class = filtersets.AnalysisThresholdFilter
    template_name = "reports/analysis_threshold/list.html"
    context_object_name = "thresholds"
    paginate_by = 5

    def get_queryset(self) -> QuerySet:
        """Return thresholds with the related component type preloaded."""
        return models.AnalysisThreshold.objects.select_related("component_type")

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity names and navigation URLs."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Analysis Threshold")
        context["entity_plural"] = _("Analysis Thresholds")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy(
            "apps.reports:analysisthreshold_create"
        )
        return context


class AnalysisThresholdDetailView(core_mixins.BaseDetailView):
    """Detail view for AnalysisThreshold model."""

    model = models.AnalysisThreshold
    permission_required = "reports.view_analysisthreshold"
    template_name = "reports/analysis_threshold/detail.html"
    context_object_name = "threshold"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URLs."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Analysis Threshold")
        context["back_url"] = reverse_lazy("apps.reports:analysisthreshold_list")
        context["edit_url"] = reverse_lazy(
            "apps.reports:analysisthreshold_update",
            kwargs={"pk": self.object.pk},
        )
        return context


class AnalysisThresholdCreateView(core_mixins.BaseCreateView):
    """Create view for AnalysisThreshold model."""

    model = models.AnalysisThreshold
    form_class = forms.AnalysisThresholdForm
    permission_required = "reports.add_analysisthreshold"
    template_name = "reports/analysis_threshold/form.html"
    success_message = _("Analysis threshold created successfully")
    success_url = reverse_lazy("apps.reports:analysisthreshold_list")

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URL."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Analysis Threshold")
        context["back_url"] = reverse_lazy("apps.reports:analysisthreshold_list")
        return context


class AnalysisThresholdUpdateView(core_mixins.BaseUpdateView):
    """Update view for AnalysisThreshold model."""

    model = models.AnalysisThreshold
    form_class = forms.AnalysisThresholdForm
    permission_required = "reports.change_analysisthreshold"
    template_name = "reports/analysis_threshold/form.html"
    success_message = _("Analysis threshold updated successfully")
    success_url = reverse_lazy("apps.reports:analysisthreshold_list")
    context_object_name = "threshold"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add entity name and navigation URL."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Analysis Threshold")
        context["back_url"] = reverse_lazy("apps.reports:analysisthreshold_list")
        return context


class AnalysisThresholdDeleteView(core_mixins.BaseDeleteView):
    """Delete view for AnalysisThreshold model using AJAX."""

    model = models.AnalysisThreshold
    permission_required = "reports.delete_analysisthreshold"
