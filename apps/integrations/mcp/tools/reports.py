"""Read-only MCP tools for laboratory reports."""

from __future__ import annotations

from django.db.models import F, Q, QuerySet
from django_mcpz.server import ToolError

from apps.reports import models as report_models

from ..permissions import scoped_queryset
from ..registry import server
from ..schemas import (
    GetReportParams,
    ListReportsParams,
    ReportDetailResult,
    ReportListResult,
)
from ._common import alert_summary, analysis_summary, report_summary


def _report_queryset(request) -> QuerySet:
    """Return the report queryset scoped to the caller's organization tree."""
    return scoped_queryset(
        request,
        report_models.Report.objects.all(),
        field="organization",
    ).select_related("laboratory", "machine", "component", "component__type")


@server.tool(
    description=(
        "Lista los reportes de laboratorio visibles para el usuario. Permite "
        "filtrar por máquina, componente, estado, condición, rango de fechas y "
        "texto libre."
    ),
    read_only=True,
    permission="reports.view_report",
)
def list_reports(request, params: ListReportsParams) -> ReportListResult:
    """Return a paginated list of reports in the caller's organization tree."""
    queryset = _report_queryset(request)
    if params.machine_id is not None:
        queryset = queryset.filter(machine_id=params.machine_id)
    if params.component_id is not None:
        queryset = queryset.filter(component_id=params.component_id)
    if params.status is not None:
        queryset = queryset.filter(status=params.status)
    if params.condition is not None:
        queryset = queryset.filter(condition=params.condition)
    if params.date_from is not None:
        queryset = queryset.filter(sample_date__gte=params.date_from)
    if params.date_to is not None:
        queryset = queryset.filter(sample_date__lte=params.date_to)
    if params.search:
        queryset = queryset.filter(
            Q(lab_number__icontains=params.search)
            | Q(per_number__icontains=params.search)
            | Q(serial_number_code__icontains=params.search)
            | Q(machine__name__icontains=params.search)
        )

    total = queryset.count()
    reports = queryset.order_by(F("sample_date").desc(nulls_last=True), "-created")[
        params.offset : params.offset + params.limit
    ]
    return ReportListResult(
        total=total,
        limit=params.limit,
        offset=params.offset,
        results=[report_summary(report) for report in reports],
    )


@server.tool(
    description=(
        "Obtiene un reporte con su análisis de laboratorio y las alertas "
        "generadas a partir de él. Usa list_reports para descubrir el id."
    ),
    read_only=True,
    permission="reports.view_report",
)
def get_report(request, params: GetReportParams) -> ReportDetailResult:
    """Return one report with its analysis and alerts."""
    report = (
        _report_queryset(request)
        .prefetch_related(
            "alerts__machine",
            "alerts__component",
            "alerts__component__type",
            "alerts__report",
        )
        .filter(pk=params.report_id)
        .first()
    )
    if report is None:
        raise ToolError("Reporte no encontrado en tu organización.")

    alerts = []
    if request.user.has_perm("alerts.view_alert"):
        alerts = [alert_summary(alert) for alert in report.alerts.all()]

    return ReportDetailResult(
        report=report_summary(report),
        analysis=analysis_summary(getattr(report, "analysis", None)),
        alerts=alerts,
    )
