"""Typed schemas for the MCP tools.

The schemas are ``msgspec.Struct`` classes so ``django-mcpz`` can generate the
tool JSON Schemas and validate every call before the ORM is touched.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

import msgspec
from django.conf import settings

ReportStatus = Literal["PENDING", "REVIEWED", "APPROVED", "REJECTED"]
ReportCondition = Literal["NORMAL", "CAUTION", "CRITICAL"]
AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]
AlertSeverity = Literal["CRITICAL", "CAUTION", "WARNING"]

DEFAULT_PAGE_SIZE = getattr(settings, "MCP_TOOL_DEFAULT_PAGE_SIZE", 25)
MAX_PAGE_SIZE = getattr(settings, "MCP_TOOL_MAX_PAGE_SIZE", 100)

Limit = Annotated[int, msgspec.Meta(ge=1, le=MAX_PAGE_SIZE)]
Offset = Annotated[int, msgspec.Meta(ge=0)]


class ComponentSummary(msgspec.Struct):
    """A component installed in a machine."""

    id: int
    type_name: str | None
    is_active: bool


class MachineSummary(msgspec.Struct):
    """A machine (equipment) visible to the token owner."""

    id: int
    name: str
    serial_number: str
    model: str
    measurement_unit: str
    measurement_unit_display: str
    branch: str | None
    fleet: str | None
    organization: str | None
    is_active: bool
    components: list[ComponentSummary] = msgspec.field(default_factory=list)


class ComponentListItem(msgspec.Struct):
    """A component row for the component listing."""

    id: int
    type_name: str | None
    machine_id: int
    machine_name: str
    is_active: bool


class ReportSummary(msgspec.Struct):
    """A compact report row."""

    id: int
    lab_number: str
    sample_date: dt.date | None
    report_date: dt.date | None
    machine: str | None
    component: str | None
    component_type: str | None
    laboratory: str | None
    condition: str
    condition_display: str
    status: str
    status_display: str
    recommendations: str
    action_required: str


class AnalysisSummary(msgspec.Struct):
    """The most relevant laboratory analysis values for an agent."""

    viscosity_40c: float | None = None
    viscosity_100c: float | None = None
    tbn: float | None = None
    tan: float | None = None
    oxidation: float | None = None
    nitration: float | None = None
    sulfation: float | None = None
    glycol: float | None = None
    fuel_dilution: float | None = None
    water_ftir: float | None = None
    pq_index: int | None = None
    particle_count_iso: str | None = None
    iron_fe: int | None = None
    chromium_cr: int | None = None
    lead_pb: int | None = None
    copper_cu: int | None = None
    tin_sn: int | None = None
    aluminum_al: int | None = None
    silicon_si: int | None = None
    sodium_na: int | None = None
    potassium_k: int | None = None
    zinc_zn: int | None = None
    calcium_ca: int | None = None
    visual_appearance: str | None = None


class AlertSummary(msgspec.Struct):
    """An alert row with the identity of its source report."""

    id: int
    machine: str | None
    component: str | None
    component_type: str | None
    category: str
    category_display: str
    severity: str
    severity_display: str
    status: str
    status_display: str
    value: float | None
    unit: str
    detected_at: dt.datetime | None
    acknowledged_at: dt.datetime | None
    resolved_at: dt.datetime | None
    report_lab_number: str | None


class EquipmentListResult(msgspec.Struct):
    """Paginated machine listing."""

    total: int
    limit: int
    offset: int
    results: list[MachineSummary]


class EquipmentDetailResult(msgspec.Struct):
    """A machine with its latest report and open alert count."""

    machine: MachineSummary
    last_report: ReportSummary | None
    open_alerts: int


class ComponentListResult(msgspec.Struct):
    """Paginated component listing."""

    total: int
    limit: int
    offset: int
    results: list[ComponentListItem]


class ReportListResult(msgspec.Struct):
    """Paginated report listing."""

    total: int
    limit: int
    offset: int
    results: list[ReportSummary]


class ReportDetailResult(msgspec.Struct):
    """A report with its laboratory analysis and alerts."""

    report: ReportSummary
    analysis: AnalysisSummary | None
    alerts: list[AlertSummary] = msgspec.field(default_factory=list)


class AlertListResult(msgspec.Struct):
    """Paginated alert listing."""

    total: int
    limit: int
    offset: int
    results: list[AlertSummary]


class AlertDetailResult(msgspec.Struct):
    """An alert with the source report identity."""

    alert: AlertSummary


class AccountOverviewResult(msgspec.Struct):
    """Orientation data for the assistant before it queries a domain."""

    organization: str | None
    organization_id: int | None
    machine_count: int
    component_count: int
    report_count: int
    open_alert_count: int
    accessible_modules: list[str]
    token_scope: str


class ListEquipmentParams(msgspec.Struct):
    """Filters for ``list_equipment``."""

    search: Annotated[
        str | None,
        msgspec.Meta(description="Texto para buscar por nombre, serie o modelo."),
    ] = None
    machine_id: Annotated[
        int | None,
        msgspec.Meta(description="Id de una máquina concreta."),
    ] = None
    include_components: bool = True
    limit: Limit = DEFAULT_PAGE_SIZE
    offset: Offset = 0


class GetEquipmentParams(msgspec.Struct):
    """Identity of the machine to inspect."""

    machine_id: Annotated[int, msgspec.Meta(description="Id de la máquina.")]


class ListComponentsParams(msgspec.Struct):
    """Filters for ``list_components``."""

    machine_id: Annotated[
        int | None,
        msgspec.Meta(description="Limita los componentes a una máquina."),
    ] = None
    search: Annotated[
        str | None,
        msgspec.Meta(description="Texto para buscar por tipo o máquina."),
    ] = None
    limit: Limit = DEFAULT_PAGE_SIZE
    offset: Offset = 0


class ListReportsParams(msgspec.Struct):
    """Filters for ``list_reports``."""

    machine_id: int | None = None
    component_id: int | None = None
    status: ReportStatus | None = None
    condition: ReportCondition | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    search: Annotated[
        str | None,
        msgspec.Meta(
            description="Busca por número de laboratorio, PER, serie o máquina."
        ),
    ] = None
    limit: Limit = DEFAULT_PAGE_SIZE
    offset: Offset = 0


class GetReportParams(msgspec.Struct):
    """Identity of the report to inspect."""

    report_id: Annotated[int, msgspec.Meta(description="Id del reporte.")]


class ListAlertsParams(msgspec.Struct):
    """Filters for ``list_alerts``."""

    machine_id: int | None = None
    component_id: int | None = None
    status: AlertStatus | None = None
    severity: AlertSeverity | None = None
    category: str | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    limit: Limit = DEFAULT_PAGE_SIZE
    offset: Offset = 0


class GetAlertParams(msgspec.Struct):
    """Identity of the alert to inspect."""

    alert_id: Annotated[int, msgspec.Meta(description="Id de la alerta.")]
