"""Serialization helpers for the MCP tools.

The helpers keep the response shape explicit: MCP clients should receive the
fields an assistant needs, not every internal column of the model.
"""

from __future__ import annotations

from typing import Any

from apps.alerts import models as alert_models
from apps.equipment import models as equipment_models
from apps.reports import models as report_models

from ..schemas import (
    AlertSummary,
    AnalysisSummary,
    ComponentListItem,
    ComponentSummary,
    MachineSummary,
    ReportSummary,
)


def _float(value: Any) -> float | None:
    """Return ``value`` as a float, preserving ``None``."""
    return float(value) if value is not None else None


def component_summary(component: equipment_models.Component) -> ComponentSummary:
    """Build a component summary."""
    return ComponentSummary(
        id=component.pk,
        type_name=component.type.name if component.type else None,
        is_active=component.is_active,
    )


def machine_summary(
    machine: equipment_models.Machine, *, include_components: bool = True
) -> MachineSummary:
    """Build a machine summary with its components."""
    components: list[ComponentSummary] = []
    if include_components:
        components = [
            component_summary(component) for component in machine.components.all()
        ]
    return MachineSummary(
        id=machine.pk,
        name=machine.name,
        serial_number=machine.serial_number,
        model=machine.model,
        measurement_unit=machine.measurement_unit,
        measurement_unit_display=machine.get_measurement_unit_display(),
        branch=machine.branch.name if machine.branch else None,
        fleet=machine.fleet.name if machine.fleet else None,
        organization=machine.organization.name if machine.organization else None,
        is_active=machine.is_active,
        components=components,
    )


def component_list_item(
    component: equipment_models.Component,
) -> ComponentListItem:
    """Build a component row for the component listing."""
    return ComponentListItem(
        id=component.pk,
        type_name=component.type.name if component.type else None,
        machine_id=component.machine_id,
        machine_name=component.machine.name,
        is_active=component.is_active,
    )


def report_summary(report: report_models.Report) -> ReportSummary:
    """Build a compact report row."""
    component = report.component
    return ReportSummary(
        id=report.pk,
        lab_number=report.lab_number,
        sample_date=report.sample_date,
        report_date=report.report_date,
        machine=report.machine.name if report.machine else None,
        component=component.type.name if component and component.type else None,
        component_type=component.type.name if component and component.type else None,
        laboratory=report.laboratory.name if report.laboratory else None,
        condition=report.condition,
        condition_display=report.get_condition_display(),
        status=report.status,
        status_display=report.get_status_display(),
        recommendations=report.recommendations,
        action_required=report.action_required,
    )


def analysis_summary(
    analysis: report_models.LabAnalysis | None,
) -> AnalysisSummary | None:
    """Build the laboratory analysis summary, if the report has one."""
    if analysis is None:
        return None
    return AnalysisSummary(
        viscosity_40c=_float(analysis.viscosity_40c),
        viscosity_100c=_float(analysis.viscosity_100c),
        tbn=_float(analysis.tbn),
        tan=_float(analysis.tan),
        oxidation=_float(analysis.oxidation),
        nitration=_float(analysis.nitration),
        sulfation=_float(analysis.sulfation),
        glycol=_float(analysis.glycol),
        fuel_dilution=_float(analysis.fuel_dilution),
        water_ftir=_float(analysis.water_ftir),
        pq_index=analysis.pq_index,
        particle_count_iso=analysis.particle_count_iso or None,
        iron_fe=analysis.iron_fe,
        chromium_cr=analysis.chromium_cr,
        lead_pb=analysis.lead_pb,
        copper_cu=analysis.copper_cu,
        tin_sn=analysis.tin_sn,
        aluminum_al=analysis.aluminum_al,
        silicon_si=analysis.silicon_si,
        sodium_na=analysis.sodium_na,
        potassium_k=analysis.potassium_k,
        zinc_zn=analysis.zinc_zn,
        calcium_ca=analysis.calcium_ca,
        visual_appearance=analysis.visual_appearance or None,
    )


def alert_summary(alert: alert_models.Alert) -> AlertSummary:
    """Build an alert row with its source report identity."""
    component = alert.component
    return AlertSummary(
        id=alert.pk,
        machine=alert.machine.name if alert.machine else None,
        component=component.type.name if component and component.type else None,
        component_type=component.type.name if component and component.type else None,
        category=alert.category,
        category_display=alert.get_category_display(),
        severity=alert.severity,
        severity_display=alert.get_severity_display(),
        status=alert.status,
        status_display=alert.get_status_display(),
        value=alert.value,
        unit=alert.unit,
        detected_at=alert.detected_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        report_lab_number=alert.report.lab_number if alert.report else None,
    )
