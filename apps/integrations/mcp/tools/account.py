"""Account orientation tool for MCP assistants."""

from __future__ import annotations

from apps.alerts import models as alert_models
from apps.equipment import models as equipment_models
from apps.reports import models as report_models

from ..permissions import request_organization, scoped_queryset
from ..registry import server
from ..schemas import AccountOverviewResult


@server.tool(
    description=(
        "Devuelve la organización del usuario, los conteos principales y los "
        "módulos a los que tiene acceso. Úsala antes de consultar equipos, "
        "reportes o alertas."
    ),
    read_only=True,
)
def get_account_overview(request) -> AccountOverviewResult:
    """Return orientation data for the authenticated user."""
    organization = request_organization(request)
    can_view_equipment = request.user.has_perm("equipment.view_machine")
    can_view_reports = request.user.has_perm("reports.view_report")
    can_view_alerts = request.user.has_perm("alerts.view_alert")

    machine_count = 0
    component_count = 0
    if can_view_equipment:
        machines = scoped_queryset(
            request,
            equipment_models.Machine.objects.filter(is_active=True),
            field="organization",
        )
        components = scoped_queryset(
            request,
            equipment_models.Component.objects.filter(
                is_active=True, machine__is_active=True
            ),
            field="machine__organization",
        )
        machine_count = machines.count()
        component_count = components.count()

    report_count = 0
    if can_view_reports:
        reports = scoped_queryset(
            request,
            report_models.Report.objects.all(),
            field="organization",
        )
        report_count = reports.count()

    open_alert_count = 0
    if can_view_alerts:
        alerts = scoped_queryset(
            request,
            alert_models.Alert.objects.filter(status="OPEN"),
            field="organization",
        )
        open_alert_count = alerts.count()

    modules: list[str] = []
    if can_view_equipment:
        modules.append("equipment")
    if can_view_reports:
        modules.append("reports")
    if can_view_alerts:
        modules.append("alerts")

    token = getattr(request, "mcp_token", None)
    return AccountOverviewResult(
        organization=organization.name if organization else None,
        organization_id=organization.pk if organization else None,
        machine_count=machine_count,
        component_count=component_count,
        report_count=report_count,
        open_alert_count=open_alert_count,
        accessible_modules=modules,
        token_scope=getattr(token, "scope", "") or "",
    )
