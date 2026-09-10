"""Business logic for the oil analysis dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Count, Max, Min, Q, QuerySet
from django.db.models.functions import TruncMonth

from apps.alerts import choices as alerts_choices
from apps.alerts import models as alerts_models
from apps.dashboard import constants
from apps.equipment import models as equipment_models
from apps.reports import choices as report_choices
from apps.reports import models as reports_models


@dataclass(frozen=True)
class DashboardFilters:
    """Validated filters applied to the dashboard querysets."""

    year: int | None = None
    fleet_id: int | None = None
    machine_id: int | None = None
    component_type_id: int | None = None


class DashboardService:
    """Aggregate oil analysis data for the dashboard."""

    def __init__(self, filters: DashboardFilters | None = None) -> None:
        """Store the dashboard filters."""
        self.filters = filters or DashboardFilters()

    def get_reports(self) -> QuerySet:
        """Return the active reports filtered by the current filters."""
        queryset = reports_models.Report.objects.filter(is_active=True)
        if self.filters.year is not None:
            queryset = queryset.filter(sample_date__year=self.filters.year)
        if self.filters.fleet_id is not None:
            queryset = queryset.filter(machine__fleet_id=self.filters.fleet_id)
        if self.filters.machine_id is not None:
            queryset = queryset.filter(machine_id=self.filters.machine_id)
        if self.filters.component_type_id is not None:
            queryset = queryset.filter(
                component__type_id=self.filters.component_type_id
            )
        return queryset

    def get_alerts(self) -> QuerySet:
        """Return the alerts filtered by the current filters."""
        queryset = alerts_models.Alert.objects.all()
        if self.filters.year is not None:
            queryset = queryset.filter(detected_at__year=self.filters.year)
        if self.filters.fleet_id is not None:
            queryset = queryset.filter(machine__fleet_id=self.filters.fleet_id)
        if self.filters.machine_id is not None:
            queryset = queryset.filter(machine_id=self.filters.machine_id)
        if self.filters.component_type_id is not None:
            queryset = queryset.filter(
                component__type_id=self.filters.component_type_id
            )
        return queryset

    def get_kpis(self, reports: QuerySet | None = None) -> dict[str, Any]:
        """Return the headline counts and non-conformance rate."""
        reports = reports if reports is not None else self.get_reports()
        counts = reports.aggregate(
            total=Count("id"),
            normal=Count(
                "id", filter=Q(condition=report_choices.ReportCondition.NORMAL)
            ),
            caution=Count(
                "id", filter=Q(condition=report_choices.ReportCondition.CAUTION)
            ),
            critical=Count(
                "id", filter=Q(condition=report_choices.ReportCondition.CRITICAL)
            ),
        )
        total = counts["total"] or 0
        non_conforming = (counts["caution"] or 0) + (counts["critical"] or 0)
        rate = round((non_conforming / total) * 100, 1) if total else 0.0
        return {
            "total": total,
            "normal": counts["normal"] or 0,
            "caution": counts["caution"] or 0,
            "critical": counts["critical"] or 0,
            "non_conformance_rate": rate,
        }

    def get_condition_distribution(
        self, reports: QuerySet | None = None
    ) -> dict[str, int]:
        """Return the number of samples per condition."""
        reports = reports if reports is not None else self.get_reports()
        result = {choice.value: 0 for choice in report_choices.ReportCondition}
        for row in reports.values("condition").annotate(total=Count("id")):
            result[row["condition"]] = row["total"]
        return result

    def get_samples_by_month(
        self, reports: QuerySet | None = None
    ) -> dict[str, list]:
        """Return monthly totals and condition splits for samples."""
        reports = reports if reports is not None else self.get_reports()
        rows = (
            reports.filter(sample_date__isnull=False)
            .annotate(month=TruncMonth("sample_date"))
            .values("month")
            .annotate(
                total=Count("id"),
                alerts=Count(
                    "id",
                    filter=Q(condition=report_choices.ReportCondition.CRITICAL),
                ),
                cautions=Count(
                    "id",
                    filter=Q(condition=report_choices.ReportCondition.CAUTION),
                ),
            )
            .order_by("month")
        )
        categories: list[str] = []
        total: list[int] = []
        alerts: list[int] = []
        cautions: list[int] = []
        for row in rows:
            categories.append(row["month"].strftime("%Y-%m"))
            total.append(row["total"])
            alerts.append(row["alerts"])
            cautions.append(row["cautions"])
        return {
            "categories": categories,
            "total": total,
            "alerts": alerts,
            "cautions": cautions,
        }

    def get_alerts_by_fleet(self, alerts: QuerySet | None = None) -> dict[str, list]:
        """Return alert counts grouped by machine fleet, sorted descending."""
        alerts = alerts if alerts is not None else self.get_alerts()
        rows = (
            alerts.values("machine__fleet__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        categories: list[str] = []
        values: list[int] = []
        for row in rows:
            categories.append(row["machine__fleet__name"] or "Sin flota")
            values.append(row["total"])
        return {"categories": categories, "values": values}

    def get_alerts_over_time(
        self, alerts: QuerySet | None = None
    ) -> dict[str, list]:
        """Return monthly alert and caution counts by detection date."""
        alerts = alerts if alerts is not None else self.get_alerts()
        rows = (
            alerts.filter(detected_at__isnull=False)
            .annotate(month=TruncMonth("detected_at"))
            .values("month")
            .annotate(
                alerts=Count(
                    "id",
                    filter=Q(severity=alerts_choices.AlertSeverity.CRITICAL),
                ),
                cautions=Count(
                    "id",
                    filter=Q(severity=alerts_choices.AlertSeverity.CAUTION),
                ),
            )
            .order_by("month")
        )
        categories: list[str] = []
        alert_values: list[int] = []
        caution_values: list[int] = []
        for row in rows:
            categories.append(row["month"].strftime("%Y-%m"))
            alert_values.append(row["alerts"])
            caution_values.append(row["cautions"])
        return {
            "categories": categories,
            "alerts": alert_values,
            "cautions": caution_values,
        }

    def get_iso4406_distribution(
        self, reports: QuerySet | None = None
    ) -> dict[str, list]:
        """Return ISO 4406 code counts and their target status."""
        reports = reports if reports is not None else self.get_reports()
        codes = (
            reports.exclude(analysis__isnull=True)
            .exclude(analysis__particle_count_iso="")
            .values_list("analysis__particle_count_iso", flat=True)
        )
        counter: dict[str, int] = {}
        for code in codes:
            counter[code] = counter.get(code, 0) + 1
        items = sorted(counter.items())
        return {
            "categories": [code for code, _ in items],
            "values": [count for _, count in items],
            "status": [
                "normal" if self._iso_is_within_target(code) else "critical"
                for code, _ in items
            ],
        }

    @staticmethod
    def _parse_iso_code(code: str) -> tuple[int, int, int] | None:
        """Parse an ``X/Y/Z`` ISO 4406 code, returning ``None`` if invalid."""
        parts = code.split("/")
        if len(parts) != 3:
            return None
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None

    @classmethod
    def _iso_is_within_target(cls, code: str) -> bool:
        """Return whether an ISO code is at or below the target limits."""
        parsed = cls._parse_iso_code(code)
        if parsed is None:
            return True
        return all(
            value <= limit
            for value, limit in zip(parsed, constants.ISO4406_TARGET_VALUES)
        )

    def get_range(self, reports: QuerySet | None = None) -> dict[str, str | None]:
        """Return the min and max sample dates as ISO strings."""
        reports = reports if reports is not None else self.get_reports()
        bounds = reports.aggregate(min=Min("sample_date"), max=Max("sample_date"))
        return {
            "min": bounds["min"].isoformat() if bounds["min"] else None,
            "max": bounds["max"].isoformat() if bounds["max"] else None,
        }

    def get_recent_reports(self, limit: int = constants.DEFAULT_RECENT_REPORTS) -> list[dict[str, Any]]:
        """Return a serialisable list of the most recent samples."""
        reports = self.get_reports().select_related(
            "machine", "machine__fleet", "component", "component__type"
        )[:limit]
        return [
            {
                "lab_number": report.lab_number,
                "machine": report.machine.name if report.machine else "",
                "fleet": (
                    report.machine.fleet.name
                    if report.machine and report.machine.fleet
                    else ""
                ),
                "component": (
                    report.component.type.name
                    if report.component and report.component.type
                    else ""
                ),
                "sample_date": (
                    report.sample_date.isoformat() if report.sample_date else ""
                ),
                "condition": report.condition,
                "condition_display": report.get_condition_display(),
                "status_display": report.get_status_display(),
            }
            for report in reports
        ]

    @staticmethod
    def get_filter_options() -> dict[str, Any]:
        """Return the available filter values."""
        years = (
            reports_models.Report.objects.filter(
                is_active=True, sample_date__isnull=False
            )
            .values_list("sample_date__year", flat=True)
            .distinct()
            .order_by("sample_date__year")
        )
        return {
            "years": [year for year in years if year is not None],
            "fleets": equipment_models.Fleet.objects.filter(is_active=True),
            "machines": equipment_models.Machine.objects.filter(is_active=True),
            "component_types": equipment_models.ComponentType.objects.filter(
                is_active=True
            ),
        }

    def build_context(self) -> dict[str, Any]:
        """Build the full JSON-serialisable dashboard payload."""
        reports = self.get_reports()
        alerts = self.get_alerts()
        kpis = self.get_kpis(reports)
        return {
            "kpis": kpis,
            "total": kpis["total"],
            "condition_distribution": self.get_condition_distribution(reports),
            "samples_by_month": self.get_samples_by_month(reports),
            "alerts_by_fleet": self.get_alerts_by_fleet(alerts),
            "alerts_over_time": self.get_alerts_over_time(alerts),
            "iso4406": self.get_iso4406_distribution(reports),
            "range": self.get_range(reports),
            "recent_reports": self.get_recent_reports(),
        }
