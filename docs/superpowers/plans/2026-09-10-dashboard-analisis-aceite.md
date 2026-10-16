# Dashboard de Análisis de Aceite — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el dashboard stub por un panel real de Análisis de Aceite con filtros, KPIs y gráficos interactivos (ApexCharts) alimentados por `Report`, `LabAnalysis`, `equipment` y `Alert`.

**Architecture:** Página server-rendered (`DashboardView`) que entrega el primer render y un endpoint JSON (`DashboardDataView`) para refrescar métricas vía AJAX. Toda la lógica de agregación vive en `DashboardService`. Los filtros usan `django-filter` (`DashboardFilter`).

**Tech Stack:** Django 6, django-filter, Tailwind v4 (TailAdmin), ApexCharts vendorizado, JavaScript vanilla, `unittest` + Factory Boy.

## Global Constraints

- Idioma UI: español vía `{% trans %}`; código (variables, funciones, docstrings, comentarios) en inglés.
- Acceso: solo `LoginRequiredMixin`, **sin** permiso específico.
- Caché: `CacheMixin` con timeout 60 s en `DashboardView`; el endpoint JSON sin caché.
- Gráficos: ApexCharts **vendorizado localmente** (sin CDN), licencia MIT.
- Timezone: `America/Lima`; usar `django.utils.timezone`.
- Referencia visual: `docs/Dashboard.png`.
- Cobertura de tests: 85 % mínimo.
- Comandos: tests `uv run python manage.py test apps.dashboard`; lint `uv run ruff check apps/dashboard`.
- **No commitear sin autorización explícita del usuario.** Al llegar a un paso de commit, pedir confirmación.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `apps/dashboard/constants.py` | Metas ISO 4406, colores, defaults |
| `apps/dashboard/services/__init__.py` | Exportar `DashboardService`, `DashboardFilters` |
| `apps/dashboard/services/dashboard_service.py` | Agregaciones y opciones de filtros |
| `apps/dashboard/filtersets.py` | `DashboardFilter` |
| `apps/dashboard/views.py` | `DashboardView`, `DashboardDataView` |
| `apps/dashboard/urls.py` | Rutas `index`, `data` |
| `apps/dashboard/tests/test_services.py` | Tests de agregaciones |
| `apps/dashboard/tests/test_filtersets.py` | Tests de filtrado |
| `apps/dashboard/tests/test_views.py` | Tests de vistas/endpoint |
| `apps/dashboard/tests/test_templates.py` | Tests de contenido de plantillas |
| `static/js/vendor/apexcharts/apexcharts.min.js` | Librería |
| `static/js/dashboard.js` | Filtros, fetch, ApexCharts, drill-down |
| `templates/dashboard/index.html` | Shell |
| `templates/dashboard/includes/filters.html` | Barra de filtros |
| `templates/dashboard/includes/kpis.html` | Tarjetas KPI |
| `templates/dashboard/includes/charts.html` | Contenedores de gráficos |
| `templates/dashboard/includes/tabs.html` | Pestañas y paneles |

---

## Task 1: Constantes y capa de servicio (`DashboardService`)

**Files:**
- Create: `apps/dashboard/constants.py`
- Create: `apps/dashboard/services/__init__.py`
- Create: `apps/dashboard/services/dashboard_service.py`
- Create: `apps/dashboard/tests/__init__.py`
- Create: `apps/dashboard/tests/test_services.py`

**Interfaces:**
- Consumes: `reports.Report`, `reports.LabAnalysis`, `alerts.Alert`, `equipment` factories.
- Produces:
  - `DashboardFilters(year: int|None, fleet_id: int|None, machine_id: int|None, component_type_id: int|None)` — dataclass frozen.
  - `DashboardService(filters: DashboardFilters|None)`
  - Métodos: `get_reports() -> QuerySet`, `get_alerts() -> QuerySet`, `get_kpis(reports=None) -> dict`, `get_condition_distribution(reports=None) -> dict[str,int]`, `get_samples_by_month(reports=None) -> dict[str,list]`, `get_alerts_by_fleet(alerts=None) -> dict[str,list]`, `get_alerts_over_time(alerts=None) -> dict[str,list]`, `get_iso4406_distribution(reports=None) -> dict[str,list]`, `get_range(reports=None) -> dict`, `get_recent_reports(limit=25) -> list[dict]`, `get_filter_options() -> dict`, `build_context() -> dict`.

- [ ] **Step 1: Crear el paquete de tests y escribir tests que fallan**

`apps/dashboard/tests/__init__.py` (vacío) y `apps/dashboard/tests/test_services.py`:

```python
"""Tests for apps.dashboard.services.dashboard_service."""

from datetime import date

from django.test import TestCase

from apps.alerts import factories as alerts_factories
from apps.dashboard.services.dashboard_service import (
    DashboardFilters,
    DashboardService,
)
from apps.equipment import factories as equipment_factories
from apps.reports import factories as reports_factories


class DashboardServiceKPITests(TestCase):
    """KPI aggregation tests."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory(name="Buque Uno")
        self.normal = reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 3, 1)
        )
        self.caution = reports_factories.ReportFactory(
            machine=self.machine, condition="CAUTION", sample_date=date(2024, 4, 1)
        )
        self.critical = reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 5, 1)
        )

    def test_kpis_counts_by_condition(self) -> None:
        """KPIs count totals per condition and compute the rate."""
        kpis = DashboardService().get_kpis()
        self.assertEqual(kpis["total"], 3)
        self.assertEqual(kpis["normal"], 1)
        self.assertEqual(kpis["caution"], 1)
        self.assertEqual(kpis["critical"], 1)
        self.assertEqual(kpis["non_conformance_rate"], 66.7)

    def test_kpis_empty_dataset(self) -> None:
        """An empty dataset returns zeros without dividing by zero."""
        kpis = DashboardService(DashboardFilters(year=1999)).get_kpis()
        self.assertEqual(kpis["total"], 0)
        self.assertEqual(kpis["non_conformance_rate"], 0.0)

    def test_condition_distribution(self) -> None:
        """Condition distribution returns one key per condition."""
        distribution = DashboardService().get_condition_distribution()
        self.assertEqual(distribution, {"NORMAL": 1, "CAUTION": 1, "CRITICAL": 1})


class DashboardServiceSeriesTests(TestCase):
    """Monthly series and grouping tests."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory(name="Buque Dos")
        self.other_machine = equipment_factories.MachineFactory(name="Buque Tres")
        reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 1, 10)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="CAUTION", sample_date=date(2024, 1, 20)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 2, 5)
        )
        alerts_factories.AlertFactory(
            report=None,
            component=None,
            machine=self.machine,
            severity="CRITICAL",
            detected_at=None,
        )

    def test_samples_by_month(self) -> None:
        """Samples are bucketed by month with alert/caution splits."""
        data = DashboardService().get_samples_by_month()
        self.assertEqual(data["categories"], ["2024-01", "2024-02"])
        self.assertEqual(data["total"], [2, 1])
        self.assertEqual(data["alerts"], [1, 0])
        self.assertEqual(data["cautions"], [1, 0])

    def test_alerts_by_fleet(self) -> None:
        """Alerts are grouped by machine fleet name, sorted desc."""
        data = DashboardService().get_alerts_by_fleet()
        self.assertEqual(data["values"], [1])
        self.assertEqual(data["categories"], [self.machine.fleet.name])

    def test_alerts_over_time_uses_detected_at(self) -> None:
        """Alerts with detected_at are bucketed; null detected_at is ignored."""
        data = DashboardService().get_alerts_over_time()
        self.assertEqual(data["categories"], [])
        self.assertEqual(data["alerts"], [])
        self.assertEqual(data["cautions"], [])


class DashboardServiceFilterTests(TestCase):
    """Filtering behaviour tests."""

    def setUp(self) -> None:
        self.fleet = equipment_factories.FleetFactory(name="Flota Sur")
        self.other_fleet = equipment_factories.FleetFactory(name="Flota Norte")
        self.machine = equipment_factories.MachineFactory(fleet=self.fleet)
        self.other_machine = equipment_factories.MachineFactory(fleet=self.other_fleet)
        self.component_type = equipment_factories.ComponentTypeFactory(name="Bomba")
        reports_factories.ReportFactory(
            machine=self.machine,
            component__type=self.component_type,
            condition="NORMAL",
            sample_date=date(2023, 6, 1),
        )
        reports_factories.ReportFactory(
            machine=self.other_machine, condition="CRITICAL", sample_date=date(2024, 6, 1)
        )

    def test_filter_by_year(self) -> None:
        """Filtering by year narrows the report queryset."""
        service = DashboardService(DashboardFilters(year=2023))
        self.assertEqual(service.get_kpis()["total"], 1)

    def test_filter_by_fleet(self) -> None:
        """Filtering by fleet narrows the report queryset."""
        service = DashboardService(DashboardFilters(fleet_id=self.fleet.pk))
        self.assertEqual(service.get_kpis()["total"], 1)

    def test_filter_by_component_type(self) -> None:
        """Filtering by component type narrows the report queryset."""
        service = DashboardService(DashboardFilters(component_type_id=self.component_type.pk))
        self.assertEqual(service.get_kpis()["total"], 1)


class DashboardServiceISOTests(TestCase):
    """ISO 4406 parsing and classification tests."""

    def setUp(self) -> None:
        self.report_ok = reports_factories.ReportFactory(condition="NORMAL")
        reports_factories.LabAnalysisFactory(
            report=self.report_ok, particle_count_iso="20/18/15"
        )
        self.report_bad = reports_factories.ReportFactory(condition="CRITICAL")
        reports_factories.LabAnalysisFactory(
            report=self.report_bad, particle_count_iso="23/21/18"
        )

    def test_iso_distribution_and_status(self) -> None:
        """ISO codes are counted and classified against the target."""
        data = DashboardService().get_iso4406_distribution()
        self.assertEqual(data["categories"], ["20/18/15", "23/21/18"])
        self.assertEqual(data["values"], [1, 1])
        self.assertEqual(data["status"], ["normal", "critical"])

    def test_iso_invalid_code_is_ignored_or_normal(self) -> None:
        """An unparseable code is treated as normal and does not crash."""
        self.assertTrue(DashboardService._iso_is_within_target("bad-code"))


class DashboardServiceAuxTests(TestCase):
    """Range, recent reports and filter options tests."""

    def setUp(self) -> None:
        self.machine = equipment_factories.MachineFactory(name="Buque Cuatro")
        reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 1, 1)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 12, 31)
        )

    def test_range(self) -> None:
        """The range exposes the min and max sample dates."""
        data = DashboardService().get_range()
        self.assertEqual(data, {"min": "2024-01-01", "max": "2024-12-31"})

    def test_recent_reports_serialisable(self) -> None:
        """Recent reports expose display values and are JSON friendly."""
        rows = DashboardService().get_recent_reports()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["machine"], "Buque Cuatro")
        self.assertIn("condition_display", rows[0])

    def test_filter_options(self) -> None:
        """Filter options expose years, fleets, machines and component types."""
        options = DashboardService.get_filter_options()
        self.assertIn(2024, options["years"])
        self.assertTrue(options["fleets"])
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `uv run python manage.py test apps.dashboard.tests.test_services`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.dashboard.services'`.

- [ ] **Step 3: Crear `apps/dashboard/constants.py`**

```python
"""Constants for the dashboard app."""

from typing import Final

ISO4406_TARGET_VALUES: Final[tuple[int, int, int]] = (22, 20, 17)

CONDITION_COLORS: Final[dict[str, str]] = {
    "NORMAL": "#12b76a",
    "CAUTION": "#FFA70B",
    "CRITICAL": "#f04438",
}

ISO4406_STATUS_COLORS: Final[dict[str, str]] = {
    "normal": "#12b76a",
    "warning": "#FFA70B",
    "critical": "#f04438",
}

DEFAULT_CACHE_TIMEOUT: Final[int] = 60
DEFAULT_RECENT_REPORTS: Final[int] = 25
```

- [ ] **Step 4: Crear `apps/dashboard/services/dashboard_service.py`**

```python
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
```

- [ ] **Step 5: Crear `apps/dashboard/services/__init__.py`**

```python
"""Dashboard services."""

from apps.dashboard.services.dashboard_service import (
    DashboardFilters,
    DashboardService,
)

__all__ = ["DashboardFilters", "DashboardService"]
```

- [ ] **Step 6: Ejecutar los tests y verificar que pasan**

Run: `uv run python manage.py test apps.dashboard.tests.test_services`
Expected: PASS (todos los tests).

- [ ] **Step 7: Commit (pedir autorización)**

```bash
git add apps/dashboard/constants.py apps/dashboard/services apps/dashboard/tests
git commit -m "feat(dashboard): add oil analysis aggregation service"
```

---

## Task 2: `DashboardFilter`

**Files:**
- Create: `apps/dashboard/filtersets.py`
- Test: `apps/dashboard/tests/test_filtersets.py`

**Interfaces:**
- Consumes: `reports.Report`, `equipment` models.
- Produces: `DashboardFilter` con campos GET `year`, `fleet`, `machine`, `component_type`.

- [ ] **Step 1: Escribir los tests que fallan**

`apps/dashboard/tests/test_filtersets.py`:

```python
"""Tests for apps.dashboard.filtersets."""

from datetime import date

from django.test import TestCase

from apps.dashboard.filtersets import DashboardFilter
from apps.equipment import factories as equipment_factories
from apps.reports import factories as reports_factories
from apps.reports import models as reports_models


class DashboardFilterTests(TestCase):
    """Filtering tests for the dashboard reports queryset."""

    def setUp(self) -> None:
        self.fleet = equipment_factories.FleetFactory(name="Flota Sur")
        self.machine = equipment_factories.MachineFactory(fleet=self.fleet)
        self.component_type = equipment_factories.ComponentTypeFactory(name="Bomba")
        self.match = reports_factories.ReportFactory(
            machine=self.machine,
            component__type=self.component_type,
            condition="NORMAL",
            sample_date=date(2023, 6, 1),
        )
        self.other = reports_factories.ReportFactory(
            condition="CRITICAL", sample_date=date(2024, 6, 1)
        )

    def test_filter_by_year(self) -> None:
        """The year filter uses the sample_date year lookup."""
        filterset = DashboardFilter({"year": 2023}, queryset=reports_models.Report.objects.all())
        self.assertIn(self.match, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_filter_by_fleet(self) -> None:
        """The fleet filter uses the machine fleet relation."""
        filterset = DashboardFilter(
            {"fleet": self.fleet.pk}, queryset=reports_models.Report.objects.all()
        )
        self.assertIn(self.match, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_filter_by_component_type(self) -> None:
        """The component type filter uses the component type relation."""
        filterset = DashboardFilter(
            {"component_type": self.component_type.pk},
            queryset=reports_models.Report.objects.all(),
        )
        self.assertIn(self.match, filterset.qs)
        self.assertNotIn(self.other, filterset.qs)

    def test_empty_filters_returns_all(self) -> None:
        """An empty filterset keeps the full queryset."""
        filterset = DashboardFilter({}, queryset=reports_models.Report.objects.all())
        self.assertEqual(filterset.qs.count(), 2)
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `uv run python manage.py test apps.dashboard.tests.test_filtersets`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.dashboard.filtersets'`.

- [ ] **Step 3: Crear `apps/dashboard/filtersets.py`**

```python
"""Filters for the dashboard app."""

from typing import ClassVar

import django_filters
from django.utils.translation import gettext_lazy as _

from apps.equipment import models as equipment_models
from apps.reports import models as reports_models


class DashboardFilter(django_filters.FilterSet):
    """Filter oil analysis samples by year, fleet, machine and component type."""

    year = django_filters.NumberFilter(
        field_name="sample_date",
        lookup_expr="year",
        label=_("Year"),
    )
    fleet = django_filters.ModelChoiceFilter(
        field_name="machine__fleet",
        queryset=equipment_models.Fleet.objects.filter(is_active=True),
        label=_("Fleet"),
    )
    machine = django_filters.ModelChoiceFilter(
        field_name="machine",
        queryset=equipment_models.Machine.objects.filter(is_active=True),
        label=_("Machine"),
    )
    component_type = django_filters.ModelChoiceFilter(
        field_name="component__type",
        queryset=equipment_models.ComponentType.objects.filter(is_active=True),
        label=_("Component Type"),
    )

    class Meta:
        model = reports_models.Report
        fields: ClassVar[list[str]] = ["year", "fleet", "machine", "component_type"]
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `uv run python manage.py test apps.dashboard.tests.test_filtersets`
Expected: PASS.

- [ ] **Step 5: Commit (pedir autorización)**

```bash
git add apps/dashboard/filtersets.py apps/dashboard/tests/test_filtersets.py
git commit -m "feat(dashboard): add dashboard filter set"
```

---

## Task 3: Vistas y URLs

**Files:**
- Modify: `apps/dashboard/views.py`
- Modify: `apps/dashboard/urls.py`
- Test: `apps/dashboard/tests/test_views.py`

**Interfaces:**
- Consumes: `DashboardService`, `DashboardFilters`, `DashboardFilter`.
- Produces:
  - Nombre de URL `apps.dashboard:index` y `apps.dashboard:data`.
  - `DashboardView` (login + caché) con contexto `dashboard_data`, `filter_options`, `last_updated`.
  - `DashboardDataView` que responde `JsonResponse` con el mismo contrato que `build_context()`.

- [ ] **Step 1: Escribir los tests que fallan**

`apps/dashboard/tests/test_views.py`:

```python
"""Tests for apps.dashboard.views."""

from datetime import date

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.dashboard.services.dashboard_service import DashboardService
from apps.equipment import factories as equipment_factories
from apps.reports import factories as reports_factories
from apps.users import factories as users_factories

DASHBOARD_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [settings.BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"dashboard/index.html": "{{ dashboard_data }}"},
                ),
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "constance.context_processors.config",
                "apps.core.context_processors.site_processor",
            ],
        },
    }
]


@override_settings(TEMPLATES=DASHBOARD_TEMPLATES)
class DashboardViewTests(TestCase):
    """Tests for the dashboard page and data endpoint."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.machine = equipment_factories.MachineFactory(name="Buque Test")
        reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 3, 1)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 4, 1)
        )

    def test_index_requires_login(self) -> None:
        """Anonymous users are redirected to login."""
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 302)

    def test_index_renders_for_logged_user(self) -> None:
        """Logged-in users can render the dashboard shell."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index.html")
        self.assertIn("dashboard_data", response.context)
        self.assertIn("filter_options", response.context)

    def test_data_requires_login(self) -> None:
        """The JSON endpoint requires authentication."""
        response = self.client.get(reverse("apps.dashboard:data"))
        self.assertEqual(response.status_code, 302)

    def test_data_returns_expected_contract(self) -> None:
        """The JSON endpoint returns the dashboard payload."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:data"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in (
            "kpis",
            "condition_distribution",
            "samples_by_month",
            "alerts_by_fleet",
            "alerts_over_time",
            "iso4406",
            "range",
            "recent_reports",
            "total",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["kpis"]["total"], 2)

    def test_data_applies_year_filter(self) -> None:
        """The JSON endpoint respects the year filter."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:data"), {"year": 2024})
        self.assertEqual(response.json()["kpis"]["total"], 2)
        response = self.client.get(reverse("apps.dashboard:data"), {"year": 2023})
        self.assertEqual(response.json()["kpis"]["total"], 0)

    def test_data_handles_invalid_filter(self) -> None:
        """An invalid filter value returns HTTP 400."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:data"), {"year": "abc"})
        self.assertEqual(response.status_code, 400)

    def test_data_query_count_is_bounded(self) -> None:
        """The endpoint avoids N+1 queries with the dataset fixed."""
        self.client.force_login(self.user)
        DashboardService()  # warm up any lazy imports
        with self.assertNumQueries(12):
            self.client.get(reverse("apps.dashboard:data"))
```

> Nota de implementación: el número exacto de `assertNumQueries` se confirmará
> empíricamente en el Step 4; ajustar el valor al real (no debe aumentar con más filas).

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `uv run python manage.py test apps.dashboard.tests.test_views`
Expected: FAIL con `NoReverseMatch` para `apps.dashboard:data`.

- [ ] **Step 3: Reescribir `apps/dashboard/views.py`**

```python
"""Views for the dashboard app."""

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import CacheMixin
from apps.dashboard import constants, filtersets
from apps.dashboard.services import DashboardFilters, DashboardService


class DashboardView(LoginRequiredMixin, CacheMixin, TemplateView):
    """Render the oil analysis dashboard shell."""

    template_name = "dashboard/index.html"
    cache_timeout = constants.DEFAULT_CACHE_TIMEOUT

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add the initial payload, filter options and timestamp."""
        context = super().get_context_data(**kwargs)
        service = DashboardService()
        context["dashboard_data"] = service.build_context()
        context["filter_options"] = service.get_filter_options()
        context["last_updated"] = timezone.now()
        return context


class DashboardDataView(LoginRequiredMixin, View):
    """Return the dashboard payload as JSON for AJAX updates."""

    def get(self, request, *args: Any, **kwargs: Any) -> JsonResponse:
        """Apply the request filters and return the JSON payload."""
        filterset = filtersets.DashboardFilter(request.GET)
        if not filterset.is_valid():
            return JsonResponse(
                {"detail": _("Invalid filters")},
                status=400,
            )
        cleaned = filterset.form.cleaned_data
        filters = DashboardFilters(
            year=cleaned.get("year"),
            fleet_id=cleaned["fleet"].pk if cleaned.get("fleet") else None,
            machine_id=cleaned["machine"].pk if cleaned.get("machine") else None,
            component_type_id=(
                cleaned["component_type"].pk
                if cleaned.get("component_type")
                else None
            ),
        )
        return JsonResponse(DashboardService(filters).build_context())
```

- [ ] **Step 4: Actualizar `apps/dashboard/urls.py`**

```python
"""URL routing for the dashboard app."""

from django.urls import path

from apps.dashboard import views

app_name = "apps.dashboard"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="index"),
    path("data/", views.DashboardDataView.as_view(), name="data"),
]
```

- [ ] **Step 5: Ejecutar y ajustar `assertNumQueries`**

Run: `uv run python manage.py test apps.dashboard.tests.test_views`
Expected: PASS. Si `test_data_query_count_is_bounded` falla, leer el valor real que reporta `assertNumQueries` y actualizarlo (debe ser constante aunque crezcan las filas). Verificar agregando más reportes que el conteo no cambia.

- [ ] **Step 6: Commit (pedir autorización)**

```bash
git add apps/dashboard/views.py apps/dashboard/urls.py apps/dashboard/tests/test_views.py
git commit -m "feat(dashboard): add dashboard shell and JSON data endpoint"
```

---

## Task 4: ApexCharts vendorizado, plantillas y JavaScript

**Files:**
- Create: `static/js/vendor/apexcharts/apexcharts.min.js`
- Create: `static/js/dashboard.js`
- Create: `templates/dashboard/includes/filters.html`
- Create: `templates/dashboard/includes/kpis.html`
- Create: `templates/dashboard/includes/charts.html`
- Create: `templates/dashboard/includes/tabs.html`
- Modify: `templates/dashboard/index.html`
- Test: `apps/dashboard/tests/test_templates.py`

**Interfaces:**
- Consumes: contexto `dashboard_data` y `filter_options`; URL `apps.dashboard:data`.
- Produces: DOM con ids `dashboard-root`, `dashboard-filters`, `dashboard-total`, `kpi-*`, `chart-*`, `tab-btn-*`, `tab-panel-*`, `dashboard-data`.

- [ ] **Step 1: Descargar ApexCharts vendorizado**

Run:
```bash
mkdir -p static/js/vendor/apexcharts
curl -fsSL "https://cdn.jsdelivr.net/npm/apexcharts@3.54.1/dist/apexcharts.min.js" -o static/js/vendor/apexcharts/apexcharts.min.js
ls -lh static/js/vendor/apexcharts/apexcharts.min.js
```
Expected: archivo > 300 KB. Si la descarga falla por red, informar al usuario y no continuar.

- [ ] **Step 2: Escribir los tests que fallan**

`apps/dashboard/tests/test_templates.py`:

```python
"""Template content tests for the dashboard app."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates" / "dashboard"
INDEX = TEMPLATE_DIR / "index.html"


class DashboardTemplateContentTests(SimpleTestCase):
    """Static checks on the dashboard template files."""

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_index_embeds_dashboard_data(self) -> None:
        """The index embeds the payload and loads the charts script."""
        content = self._read(INDEX)
        self.assertIn("dashboard-data", content)
        self.assertIn("js/dashboard.js", content)
        self.assertIn("apexcharts.min.js", content)

    def test_kpis_include_expected_labels(self) -> None:
        """KPI cards expose the expected (English msgid) labels."""
        content = self._read(TEMPLATE_DIR / "includes" / "kpis.html")
        for label in ("Total Samples", "Normal", "Precaution", "Non-Conformance Rate"):
            self.assertIn(label, content)

    def test_placeholder_data_removed(self) -> None:
        """The old hardcoded placeholder values are gone."""
        content = self._read(INDEX)
        for value in ("$3.456K", "45.2K", "Total Profit", "Welcome back"):
            self.assertNotIn(value, content)

    def test_tabs_are_present(self) -> None:
        """All expected tabs are rendered (English msgids; translated at runtime)."""
        content = self._read(TEMPLATE_DIR / "includes" / "tabs.html")
        for label in ("Summary", "Trends", "Wear", "Contamination", "Oil Health", "Alerts", "Data Table", "References"):
            self.assertIn(label, content)
```

- [ ] **Step 3: Ejecutar y verificar que fallan**

Run: `uv run python manage.py test apps.dashboard.tests.test_templates`
Expected: FAIL (`templates/dashboard/includes/kpis.html` no existe).

- [ ] **Step 4: Crear `templates/dashboard/index.html`**

```django
{% extends "layouts/dashboard.html" %}
{% load static %}
{% load i18n %}

{% block title_page %}{% trans "Oil Analysis" %}{% endblock title_page %}
{% block toolbar_title %}{% trans "Oil Analysis" %}{% endblock %}

{% block content %}
<div
    id="dashboard-root"
    data-data-url="{% url 'apps.dashboard:data' %}"
    class="flex flex-col gap-6"
>
    {% include "dashboard/includes/filters.html" %}
    {% include "dashboard/includes/tabs.html" %}
</div>

{{ dashboard_data|json_script:"dashboard-data" }}
{% endblock content %}

{% block extra_js %}
<script src="{% static 'js/vendor/apexcharts/apexcharts.min.js' %}"></script>
<script src="{% static 'js/dashboard.js' %}"></script>
{% endblock extra_js %}
```

- [ ] **Step 5: Crear `templates/dashboard/includes/filters.html`**

```django
{% load i18n %}
<div class="rounded-2xl border border-gray-200 bg-white p-4 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
    <form id="dashboard-filters" class="flex flex-wrap items-end gap-3">
        <label class="flex flex-col gap-1">
            <span class="text-xs font-medium text-gray-500">{% trans "Year" %}</span>
            <select name="year" class="rounded-lg border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-700 dark:text-white">
                <option value="">{% trans "All" %}</option>
                {% for year in filter_options.years %}
                <option value="{{ year }}">{{ year }}</option>
                {% endfor %}
            </select>
        </label>
        <label class="flex flex-col gap-1">
            <span class="text-xs font-medium text-gray-500">{% trans "Fleet" %}</span>
            <select name="fleet" class="rounded-lg border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-700 dark:text-white">
                <option value="">{% trans "All" %}</option>
                {% for fleet in filter_options.fleets %}
                <option value="{{ fleet.pk }}">{{ fleet.name }}</option>
                {% endfor %}
            </select>
        </label>
        <label class="flex flex-col gap-1">
            <span class="text-xs font-medium text-gray-500">{% trans "Machine" %}</span>
            <select name="machine" class="rounded-lg border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-700 dark:text-white">
                <option value="">{% trans "All" %}</option>
                {% for machine in filter_options.machines %}
                <option value="{{ machine.pk }}">{{ machine.name }}</option>
                {% endfor %}
            </select>
        </label>
        <label class="flex flex-col gap-1">
            <span class="text-xs font-medium text-gray-500">{% trans "Component" %}</span>
            <select name="component_type" class="rounded-lg border border-gray-200 bg-transparent px-3 py-2 text-sm dark:border-gray-700 dark:text-white">
                <option value="">{% trans "All" %}</option>
                {% for component_type in filter_options.component_types %}
                <option value="{{ component_type.pk }}">{{ component_type.name }}</option>
                {% endfor %}
            </select>
        </label>
        <button type="button" id="dashboard-reset" class="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-white dark:hover:bg-white/5">
            {% trans "Reset" %}
        </button>
        <div class="ml-auto flex items-center gap-4 text-sm text-gray-500">
            <span id="dashboard-total">{{ dashboard_data.total }} {% trans "samples" %}</span>
            <span id="dashboard-range" class="italic">
                {% if dashboard_data.range.min %}{{ dashboard_data.range.min }} &rarr; {{ dashboard_data.range.max }}{% endif %}
            </span>
        </div>
    </form>
</div>
```

- [ ] **Step 6: Crear `templates/dashboard/includes/kpis.html`**

```django
{% load i18n %}
<div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <div class="mb-3 h-1 w-10 rounded-full bg-primary"></div>
        <span class="text-xs font-semibold uppercase text-gray-500">{% trans "Total Samples" %}</span>
        <p id="kpi-total" class="mt-1 text-3xl font-bold text-black dark:text-white">{{ dashboard_data.kpis.total }}</p>
        <span class="text-xs text-gray-500">{{ dashboard_data.total }} {% trans "records" %}</span>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <div class="mb-3 h-1 w-10 rounded-full bg-success"></div>
        <span class="text-xs font-semibold uppercase text-gray-500">{% trans "Normal" %}</span>
        <p id="kpi-normal" class="mt-1 text-3xl font-bold text-success">{{ dashboard_data.kpis.normal }}</p>
        <span class="text-xs text-gray-500">{{ dashboard_data.kpis.normal|floatformat:0 }} {% trans "samples" %}</span>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <div class="mb-3 h-1 w-10 rounded-full bg-warning"></div>
        <span class="text-xs font-semibold uppercase text-gray-500">{% trans "Precaution" %}</span>
        <p id="kpi-caution" class="mt-1 text-3xl font-bold text-warning">{{ dashboard_data.kpis.caution }}</p>
        <span class="text-xs text-gray-500">{% trans "monitor" %}</span>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <div class="mb-3 h-1 w-10 rounded-full bg-error"></div>
        <span class="text-xs font-semibold uppercase text-gray-500">{% trans "Alert" %}</span>
        <p id="kpi-critical" class="mt-1 text-3xl font-bold text-error">{{ dashboard_data.kpis.critical }}</p>
        <span class="text-xs text-gray-500">{% trans "action required" %}</span>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <div class="mb-3 h-1 w-10 rounded-full bg-warning"></div>
        <span class="text-xs font-semibold uppercase text-gray-500">{% trans "Non-Conformance Rate" %}</span>
        <p id="kpi-rate" class="mt-1 text-3xl font-bold text-warning">{{ dashboard_data.kpis.non_conformance_rate }}%</p>
        <span class="text-xs text-gray-500">{% trans "alert + precaution" %}</span>
    </div>
</div>
```

- [ ] **Step 7: Crear `templates/dashboard/includes/charts.html`**

```django
{% load i18n %}
<div class="grid grid-cols-1 gap-4 xl:grid-cols-3">
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <h3 class="mb-2 text-base font-semibold text-black dark:text-white">{% trans "Condition Distribution" %}</h3>
        <div id="chart-condition" aria-label="{% trans 'Condition distribution' %}"></div>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg xl:col-span-2 dark:border-gray-800 dark:bg-gray-dark">
        <h3 class="mb-2 text-base font-semibold text-black dark:text-white">{% trans "Samples per Month" %}</h3>
        <div id="chart-samples" aria-label="{% trans 'Samples per month' %}"></div>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <h3 class="mb-2 text-base font-semibold text-black dark:text-white">{% trans "Alerts by Fleet" %}</h3>
        <div id="chart-fleet" aria-label="{% trans 'Alerts by fleet' %}"></div>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <h3 class="mb-2 text-base font-semibold text-black dark:text-white">{% trans "Alerts over Time" %}</h3>
        <div id="chart-alerts-time" aria-label="{% trans 'Alerts over time' %}"></div>
    </div>
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
        <h3 class="mb-2 text-base font-semibold text-black dark:text-white">{% trans "ISO 4406 Distribution" %}</h3>
        <div id="chart-iso" aria-label="{% trans 'ISO 4406 distribution' %}"></div>
    </div>
</div>
```

- [ ] **Step 8: Crear `templates/dashboard/includes/tabs.html`**

```django
{% load i18n %}
<div class="rounded-2xl border border-gray-200 bg-white shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark">
    <div class="flex flex-wrap gap-1 border-b border-gray-200 px-2 pt-2 dark:border-gray-800">
        <button type="button" class="tab-btn rounded-t-lg px-4 py-2 text-sm font-medium" data-tab="resumen">{% trans "Summary" %}</button>
        <button type="button" class="tab-btn rounded-t-lg px-4 py-2 text-sm font-medium" data-tab="tendencias">{% trans "Trends" %}</button>
        <button type="button" class="tab-btn rounded-t-lg px-4 py-2 text-sm font-medium" data-tab="desgaste">{% trans "Wear" %}</button>
        <button type="button" class="tab-btn rounded-t-lg px-4 py-2 text-sm font-medium" data-tab="contaminacion">{% trans "Contamination" %}</button>
        <button type="button" class="tab-btn rounded-t-lg px-4 py-2 text-sm font-medium" data-tab="estado">{% trans "Oil Health" %}</button>
        <a href="{% url 'apps.alerts:alert_list' %}" class="rounded-t-lg px-4 py-2 text-sm font-medium text-gray-500 hover:text-primary">{% trans "Alerts" %}</a>
        <button type="button" class="tab-btn rounded-t-lg px-4 py-2 text-sm font-medium" data-tab="datos">{% trans "Data Table" %}</button>
        <button type="button" class="tab-btn rounded-t-lg px-4 py-2 text-sm font-medium" data-tab="referencias">{% trans "References" %}</button>
    </div>

    <div class="p-4">
        <div id="tab-panel-resumen" class="tab-panel flex flex-col gap-6">
            {% include "dashboard/includes/kpis.html" %}
            {% include "dashboard/includes/charts.html" %}
        </div>
        <div id="tab-panel-tendencias" class="tab-panel hidden">
            <p class="text-sm text-gray-500">{% trans "Trend analysis will reuse the monthly series above." %}</p>
        </div>
        <div id="tab-panel-desgaste" class="tab-panel hidden">
            <p class="text-sm text-gray-500">{% trans "Wear metal trends (Fe, Cu, Al, Cr, Pb)." %}</p>
        </div>
        <div id="tab-panel-contaminacion" class="tab-panel hidden">
            <p class="text-sm text-gray-500">{% trans "Contaminants (Si, Na, K) and water/fuel ingress." %}</p>
        </div>
        <div id="tab-panel-estado" class="tab-panel hidden">
            <p class="text-sm text-gray-500">{% trans "Viscosity, TBN/TAN and oxidation status." %}</p>
        </div>
        <div id="tab-panel-datos" class="tab-panel hidden">
            <h3 class="mb-3 text-base font-semibold text-black dark:text-white">{% trans "Recent Samples" %}</h3>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead class="text-xs uppercase text-gray-500">
                        <tr>
                            <th class="px-3 py-2">{% trans "Lab No." %}</th>
                            <th class="px-3 py-2">{% trans "Machine" %}</th>
                            <th class="px-3 py-2">{% trans "Fleet" %}</th>
                            <th class="px-3 py-2">{% trans "Component" %}</th>
                            <th class="px-3 py-2">{% trans "Date" %}</th>
                            <th class="px-3 py-2">{% trans "Condition" %}</th>
                        </tr>
                    </thead>
                    <tbody id="dashboard-table-body">
                        {% for row in dashboard_data.recent_reports %}
                        <tr class="border-t border-gray-100 dark:border-gray-800" data-condition="{{ row.condition }}">
                            <td class="px-3 py-2">{{ row.lab_number }}</td>
                            <td class="px-3 py-2">{{ row.machine }}</td>
                            <td class="px-3 py-2">{{ row.fleet }}</td>
                            <td class="px-3 py-2">{{ row.component }}</td>
                            <td class="px-3 py-2">{{ row.sample_date }}</td>
                            <td class="px-3 py-2">{{ row.condition_display }}</td>
                        </tr>
                        {% empty %}
                        <tr><td colspan="6" class="px-3 py-6 text-center text-gray-500">{% trans "No samples found." %}</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <div id="tab-panel-referencias" class="tab-panel hidden">
            <p class="text-sm text-gray-500">{% trans "ISO 4406 target" %}: &le; 22/20/17. {% trans "Codes above the limit are flagged in red." %}</p>
        </div>
    </div>
</div>
```

- [ ] **Step 9: Crear `static/js/dashboard.js`**

```javascript
(function () {
    "use strict";

    var root = document.getElementById("dashboard-root");
    if (!root) {
        return;
    }

    var dataUrl = root.getAttribute("data-data-url");
    var dataElement = document.getElementById("dashboard-data");
    var currentData = dataElement ? JSON.parse(dataElement.textContent) : {};
    var charts = {};

    var COLORS = { NORMAL: "#12b76a", CAUTION: "#FFA70B", CRITICAL: "#f04438" };

    function isDark() {
        return document.documentElement.classList.contains("dark");
    }

    function baseOptions() {
        return {
            chart: {
                toolbar: { show: false },
                background: "transparent",
                fontFamily: "Outfit, sans-serif",
                foreColor: isDark() ? "#AEB7C0" : "#64748B"
            },
            theme: { mode: isDark() ? "dark" : "light" },
            dataLabels: { enabled: false },
            grid: { borderColor: isDark() ? "#2E3A47" : "#E2E8F0" }
        };
    }

    function renderConditionChart(data) {
        var el = document.getElementById("chart-condition");
        if (!el) return;
        charts.condition = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "donut", height: 280 }),
            labels: ["Normal", "Precaución", "Alerta"],
            series: [
                data.condition_distribution.NORMAL || 0,
                data.condition_distribution.CAUTION || 0,
                data.condition_distribution.CRITICAL || 0
            ],
            colors: [COLORS.NORMAL, COLORS.CAUTION, COLORS.CRITICAL],
            legend: { position: "bottom" }
        }));
        charts.condition.render();
    }

    function renderSamplesChart(data) {
        var el = document.getElementById("chart-samples");
        if (!el) return;
        charts.samples = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "line", height: 280 }),
            series: [
                { name: "Total", data: data.samples_by_month.total },
                { name: "Alerta", data: data.samples_by_month.alerts },
                { name: "Precaución", data: data.samples_by_month.cautions }
            ],
            colors: ["#465fff", COLORS.CRITICAL, COLORS.CAUTION],
            stroke: { curve: "smooth", width: 2 },
            xaxis: { categories: data.samples_by_month.categories }
        }));
        charts.samples.render();
    }

    function renderFleetChart(data) {
        var el = document.getElementById("chart-fleet");
        if (!el) return;
        charts.fleet = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "bar", height: 280 }),
            series: [{ name: "Alertas", data: data.alerts_by_fleet.values }],
            colors: [COLORS.CAUTION],
            plotOptions: { bar: { horizontal: true, borderRadius: 4 } },
            xaxis: { categories: data.alerts_by_fleet.categories }
        }));
        charts.fleet.render();
    }

    function renderAlertsTimeChart(data) {
        var el = document.getElementById("chart-alerts-time");
        if (!el) return;
        charts.alertsTime = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "line", height: 280 }),
            series: [
                { name: "Alertas", data: data.alerts_over_time.alerts },
                { name: "Precauciones", data: data.alerts_over_time.cautions }
            ],
            colors: [COLORS.CRITICAL, COLORS.CAUTION],
            stroke: { curve: "smooth", width: 2 },
            xaxis: { categories: data.alerts_over_time.categories }
        }));
        charts.alertsTime.render();
    }

    function renderIsoChart(data) {
        var el = document.getElementById("chart-iso");
        if (!el) return;
        charts.iso = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "bar", height: 280 }),
            series: [{ name: "Muestras", data: data.iso4406.values }],
            colors: data.iso4406.status.map(function (status) {
                return status === "normal" ? COLORS.NORMAL : COLORS.CRITICAL;
            }),
            plotOptions: { bar: { columnWidth: "55%", borderRadius: 4, distributed: true } },
            legend: { show: false },
            xaxis: { categories: data.iso4406.categories }
        }));
        charts.iso.render();
    }

    function destroyCharts() {
        Object.keys(charts).forEach(function (key) {
            if (charts[key]) {
                charts[key].destroy();
            }
        });
        charts = {};
    }

    function renderAll(data) {
        currentData = data;
        destroyCharts();
        renderConditionChart(data);
        renderSamplesChart(data);
        renderFleetChart(data);
        renderAlertsTimeChart(data);
        renderIsoChart(data);
    }

    function updateKpis(kpis) {
        var mapping = {
            "kpi-total": kpis.total,
            "kpi-normal": kpis.normal,
            "kpi-caution": kpis.caution,
            "kpi-critical": kpis.critical,
            "kpi-rate": kpis.non_conformance_rate + "%"
        };
        Object.keys(mapping).forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.textContent = mapping[id];
        });
    }

    function updateSummary(data) {
        var total = document.getElementById("dashboard-total");
        if (total) total.textContent = data.total + " muestras";
        var range = document.getElementById("dashboard-range");
        if (range && data.range.min) {
            range.textContent = data.range.min + " → " + data.range.max;
        }
    }

    function applyData(data) {
        updateKpis(data.kpis);
        updateSummary(data);
        renderAll(data);
    }

    function currentFilters() {
        var form = document.getElementById("dashboard-filters");
        var params = new URLSearchParams();
        if (!form) return params;
        Array.prototype.forEach.call(form.elements, function (field) {
            if (field.name && field.value) params.append(field.name, field.value);
        });
        return params;
    }

    function refresh() {
        fetch(dataUrl + "?" + currentFilters().toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (response) { return response.json(); })
            .then(applyData)
            .catch(function () { /* keep previous data on error */ });
    }

    function setupTabs() {
        var buttons = document.querySelectorAll(".tab-btn");
        Array.prototype.forEach.call(buttons, function (button) {
            button.addEventListener("click", function () {
                var target = button.getAttribute("data-tab");
                Array.prototype.forEach.call(buttons, function (other) {
                    other.classList.toggle("bg-gray-100", other === button);
                    other.classList.toggle("text-primary", other === button);
                    other.classList.toggle("dark:bg-white/[0.05]", other === button);
                });
                Array.prototype.forEach.call(document.querySelectorAll(".tab-panel"), function (panel) {
                    panel.classList.toggle("hidden", panel.id !== "tab-panel-" + target);
                });
            });
        });
        var first = document.querySelector('.tab-btn[data-tab="resumen"]');
        if (first) first.click();
    }

    function setupFilters() {
        var form = document.getElementById("dashboard-filters");
        if (form) {
            Array.prototype.forEach.call(form.elements, function (field) {
                if (field.tagName === "SELECT") field.addEventListener("change", refresh);
            });
        }
        var reset = document.getElementById("dashboard-reset");
        if (reset) {
            reset.addEventListener("click", function () {
                if (form) {
                    Array.prototype.forEach.call(form.elements, function (field) {
                        if (field.tagName === "SELECT") field.value = "";
                    });
                }
                refresh();
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupTabs();
        setupFilters();
        renderAll(currentData);
    });
})();
```

- [ ] **Step 10: Ejecutar los tests de plantillas y los checks**

Run:
```bash
uv run python manage.py test apps.dashboard.tests.test_templates
uv run python manage.py check
```
Expected: PASS y `System check identified no issues`.

- [ ] **Step 11: Commit (pedir autorización)**

```bash
git add static/js/vendor/apexcharts static/js/dashboard.js templates/dashboard
git commit -m "feat(dashboard): add oil analysis dashboard UI with ApexCharts"
```

---

## Task 5: Internacionalización

**Files:**
- Modify: `locale/es/LC_MESSAGES/django.po`
- Modify: `locale/en/LC_MESSAGES/django.po`

- [ ] **Step 1: Regenerar catálogos**

Run:
```bash
uv run python manage.py makemessages -l es -l en --ignore=.venv --ignore=node_modules
```
Expected: `locale/es/LC_MESSAGES/django.po` y `locale/en/LC_MESSAGES/django.po` actualizados con las nuevas cadenas del dashboard.

- [ ] **Step 2: Traducir las cadenas nuevas**

Editar las entradas nuevas en ambos `.po` (msgstr en español para `es`, en inglés para `en`). Cadenas esperadas: `Oil Analysis`, `Year`, `Fleet`, `Machine`, `Component`, `Reset`, `Total Samples`, `Normal`, `Precaution`, `Alert`, `Non-Conformance Rate`, `Condition Distribution`, `Samples per Month`, `Alerts by Fleet`, `Alerts over Time`, `ISO 4406 Distribution`, `Summary`, `Trends`, `Wear`, `Contamination`, `Oil Health`, `Data Table`, `References`, `Recent Samples`, `No samples found.`.

- [ ] **Step 3: Compilar mensajes**

Run: `uv run python manage.py compilemessages`
Expected: `processing file ... django.po` para cada idioma, sin errores.

- [ ] **Step 4: Commit (pedir autorización)**

```bash
git add locale
git commit -m "chore(dashboard): update es/en translation catalogs"
```

---

## Task 6: Limpieza, verificación y revisión final

**Files:**
- Modify: cualquier archivo con código muerto detectado.

- [ ] **Step 1: Limpieza de código sin uso**

Revisar y eliminar:
- Restos de las tarjetas placeholder en `templates/dashboard/*` (ya cubierto por la reescritura; confirmar con el test `test_placeholder_data_removed`).
- Imports/contexto muertos en `apps/dashboard/views.py`.
- Confirmar que `apps/dashboard/models.py` sigue vacío y que no hay imports huérfanos.

Run: `uv run ruff check apps/dashboard --fix`
Expected: sin errores.

- [ ] **Step 2: Ejecutar la suite completa del dashboard**

Run: `uv run python manage.py test apps.dashboard --verbosity=2`
Expected: todos los tests PASS.

- [ ] **Step 3: Cobertura**

Run:
```bash
uv run coverage run manage.py test apps.dashboard
uv run coverage report --include="apps/dashboard/*"
```
Expected: cobertura ≥ 85 % en `apps/dashboard`.

- [ ] **Step 4: Revisión con `django-reviewer`**

Cargar la skill `django-reviewer` y revisar los archivos modificados/creados de `apps/dashboard` (informe de hallazgos). Aplicar solo refinamientos que no cambien el comportamiento y que respeten las convenciones del proyecto. Volver a ejecutar los tests tras cualquier ajuste.

- [ ] **Step 5: Verificación manual en navegador (si es posible)**

Levantar el servidor (`uv run python manage.py runserver`), iniciar sesión y comprobar:
- KPIs y gráficos cargan con datos reales.
- Cambiar filtros y Reset actualiza KPIs/series sin recargar.
- Navegación entre pestañas y drill-down visual básico.
- Modo oscuro coherente.

- [ ] **Step 6: Commit final (pedir autorización)**

```bash
git add -A
git commit -m "refactor(dashboard): remove dead code and finalize oil analysis dashboard"
```

---

## Self-review (cobertura del spec)

| Requisito del spec | Task |
|---|---|
| KPIs (5) y tasa no conforme | Task 1 |
| Distribución por condición | Task 1 |
| Muestras por mes | Task 1 |
| Alertas por flota | Task 1 |
| Alertas en el tiempo | Task 1 |
| ISO 4406 | Task 1 |
| Filtros año/flota/equipo/componente | Task 2 |
| Vista shell + endpoint JSON | Task 3 |
| Login obligatorio | Task 3 |
| ApexCharts vendorizado + UI + pestañas + drill-down | Task 4 |
| Tabla Datos | Task 4 |
| i18n es/en | Task 5 |
| Eliminar código sin uso | Task 6 |
| Tests (85 %) | Tasks 1–4, 6 |
| Revisión con django-reviewer | Task 6 |

Sin marcadores de posición pendientes. Firmas consistentes entre tasks (`DashboardService`, `DashboardFilters`, `build_context`, ids de DOM).
