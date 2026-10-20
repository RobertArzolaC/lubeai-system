"""Read-only MCP tools for alerts."""

from __future__ import annotations

from django.db.models import F
from django_mcpz.server import ToolError

from apps.alerts import models as alert_models

from ..permissions import scoped_queryset
from ..registry import server
from ..schemas import (
    AlertDetailResult,
    AlertListResult,
    GetAlertParams,
    ListAlertsParams,
)
from ._common import alert_summary


@server.tool(
    description=(
        "Lista las alertas visibles para el usuario. Permite filtrar por "
        "máquina, componente, estado, severidad, categoría y rango de fechas."
    ),
    read_only=True,
    permission="alerts.view_alert",
)
def list_alerts(request, params: ListAlertsParams) -> AlertListResult:
    """Return a paginated list of alerts in the caller's organization tree."""
    queryset = scoped_queryset(
        request,
        alert_models.Alert.objects.all(),
        field="organization",
    ).select_related("machine", "component", "component__type", "report")
    if params.machine_id is not None:
        queryset = queryset.filter(machine_id=params.machine_id)
    if params.component_id is not None:
        queryset = queryset.filter(component_id=params.component_id)
    if params.status is not None:
        queryset = queryset.filter(status=params.status)
    if params.severity is not None:
        queryset = queryset.filter(severity=params.severity)
    if params.category:
        queryset = queryset.filter(category=params.category)
    if params.date_from is not None:
        queryset = queryset.filter(detected_at__date__gte=params.date_from)
    if params.date_to is not None:
        queryset = queryset.filter(detected_at__date__lte=params.date_to)

    total = queryset.count()
    alerts = queryset.order_by(F("detected_at").desc(nulls_last=True), "-created")[
        params.offset : params.offset + params.limit
    ]
    return AlertListResult(
        total=total,
        limit=params.limit,
        offset=params.offset,
        results=[alert_summary(alert) for alert in alerts],
    )


@server.tool(
    description=(
        "Obtiene el detalle de una alerta y el número de laboratorio del "
        "reporte que la originó. Usa list_alerts para descubrir el id."
    ),
    read_only=True,
    permission="alerts.view_alert",
)
def get_alert(request, params: GetAlertParams) -> AlertDetailResult:
    """Return one alert with its source report identity."""
    alert = (
        scoped_queryset(
            request,
            alert_models.Alert.objects.all(),
            field="organization",
        )
        .select_related("machine", "component", "component__type", "report")
        .filter(pk=params.alert_id)
        .first()
    )
    if alert is None:
        raise ToolError("Alerta no encontrada en tu organización.")
    return AlertDetailResult(alert=alert_summary(alert))
