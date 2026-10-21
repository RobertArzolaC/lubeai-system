"""Read-only MCP tools for equipment and components."""

from __future__ import annotations

from django.db.models import F, Q
from django_mcpz.server import ToolError

from apps.alerts import choices as alert_choices
from apps.equipment import models as equipment_models

from ..permissions import scoped_queryset
from ..registry import server
from ..schemas import (
    ComponentListResult,
    EquipmentDetailResult,
    EquipmentListResult,
    GetEquipmentParams,
    ListComponentsParams,
    ListEquipmentParams,
)
from ._common import (
    component_list_item,
    machine_summary,
    report_summary,
)


@server.tool(
    description=(
        "Lista los equipos (máquinas) visibles para el usuario. Permite buscar "
        "por nombre, número de serie o modelo y elegir si se incluyen los "
        "componentes de cada equipo."
    ),
    read_only=True,
    permission="equipment.view_machine",
)
def list_equipment(request, params: ListEquipmentParams) -> EquipmentListResult:
    """Return a paginated list of machines in the caller's organization tree."""
    queryset = scoped_queryset(
        request,
        equipment_models.Machine.objects.filter(is_active=True),
        field="organization",
    ).select_related("branch", "fleet", "organization")
    if params.include_components:
        queryset = queryset.prefetch_related("components__type")
    if params.machine_id is not None:
        queryset = queryset.filter(pk=params.machine_id)
    if params.search:
        queryset = queryset.filter(
            Q(name__icontains=params.search)
            | Q(serial_number__icontains=params.search)
            | Q(model__icontains=params.search)
        )

    total = queryset.count()
    machines = queryset.order_by("name")[params.offset : params.offset + params.limit]
    return EquipmentListResult(
        total=total,
        limit=params.limit,
        offset=params.offset,
        results=[
            machine_summary(machine, include_components=params.include_components)
            for machine in machines
        ],
    )


@server.tool(
    description=(
        "Obtiene el detalle de un equipo, sus componentes, su último reporte y "
        "el número de alertas abiertas."
    ),
    read_only=True,
    permission="equipment.view_machine",
)
def get_equipment(request, params: GetEquipmentParams) -> EquipmentDetailResult:
    """Return one machine with its components and latest report."""
    queryset = scoped_queryset(
        request,
        equipment_models.Machine.objects.filter(is_active=True),
        field="organization",
    ).select_related("branch", "fleet", "organization")
    machine = (
        queryset.prefetch_related("components__type")
        .filter(pk=params.machine_id)
        .first()
    )
    if machine is None:
        raise ToolError("Equipo no encontrado en tu organización.")

    last_report = None
    if request.user.has_perm("reports.view_report"):
        last_report = (
            machine.reports.select_related(
                "laboratory", "machine", "component", "component__type"
            )
            .order_by(F("sample_date").desc(nulls_last=True), "-created")
            .first()
        )

    open_alerts = 0
    if request.user.has_perm("alerts.view_alert"):
        open_alerts = machine.alerts.filter(
            status=alert_choices.AlertStatus.OPEN
        ).count()

    return EquipmentDetailResult(
        machine=machine_summary(machine),
        last_report=report_summary(last_report) if last_report else None,
        open_alerts=open_alerts,
    )


@server.tool(
    description=(
        "Lista los componentes visibles para el usuario, opcionalmente "
        "limitados a una máquina. Devuelve el tipo de componente y la máquina "
        "a la que pertenece."
    ),
    read_only=True,
    permission="equipment.view_machine",
)
def list_components(request, params: ListComponentsParams) -> ComponentListResult:
    """Return a paginated list of components in the caller's organization tree."""
    queryset = scoped_queryset(
        request,
        equipment_models.Component.objects.filter(
            is_active=True, machine__is_active=True
        ),
        field="machine__organization",
    ).select_related("machine", "type")
    if params.machine_id is not None:
        queryset = queryset.filter(machine_id=params.machine_id)
    if params.search:
        queryset = queryset.filter(
            Q(type__name__icontains=params.search)
            | Q(machine__name__icontains=params.search)
            | Q(machine__serial_number__icontains=params.search)
        )

    total = queryset.count()
    components = queryset.order_by("machine__name", "type__name")[
        params.offset : params.offset + params.limit
    ]
    return ComponentListResult(
        total=total,
        limit=params.limit,
        offset=params.offset,
        results=[component_list_item(component) for component in components],
    )
