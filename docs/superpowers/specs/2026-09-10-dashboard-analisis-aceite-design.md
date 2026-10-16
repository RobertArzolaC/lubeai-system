# Diseño: Dashboard de Análisis de Aceite

- **Fecha:** 2026-09-10
- **Estado:** Aprobado
- **Referencia visual:** `docs/Dashboard.png`
- **Alcance:** Resumen completo + base de pestañas (resto de pestañas con contenido básico real)
- **Idioma:** UI en español vía `{% trans %}`; código en inglés (AGENTS.md)

## 1. Objetivo

Reemplazar el dashboard stub (`DashboardView` con KPIs ficticios hardcodeados) por un
panel real de **Análisis de Aceite** que agregue datos de `reports.Report` +
`reports.LabAnalysis`, `equipment` y `alerts.Alert`, con filtros, KPIs y gráficos
interactivos, siguiendo la referencia `docs/Dashboard.png`.

## 2. Contexto actual (hallazgos)

- `apps/dashboard/views.py`: `DashboardView(CacheMixin, TemplateView)`, sin login ni permisos.
- `apps/dashboard/models.py`: vacío.
- `templates/dashboard/index.html`: datos ficticios (`$3.456K`, `45.2K`, …) y sección de bienvenida.
- No hay librería de gráficos instalada.
- Patrones existentes a reutilizar: capa de servicios (`ReportExportService`, `AlertService`),
  mixins (`BaseListView`, `CacheMixin`, `LoginRequiredMixin`), `django-filter`, factories y
  tests estilo `unittest` con `TEMPLATES` en `locmem`.
- Tailwind v4 con tokens: `primary`, `success`, `warning`, `error`, `gray-*`, `boxdark`.
- `LANGUAGE_CODE = "es-pe"`, `TIME_ZONE = "America/Lima"`, `USE_TZ = True`.

## 3. Decisiones acordadas

| Tema | Decisión |
|------|----------|
| Alcance | Resumen completo; demás pestañas como estructura navegable con contenido básico |
| Gráficos | ApexCharts vendorizado localmente (MIT, sin CDN) |
| Arquitectura | Página server-rendered + endpoint JSON (AJAX) |
| Acceso | Solo login (`LoginRequiredMixin`), sin permiso específico |
| Idioma | UI en español vía `{% trans %}`; código en inglés |

## 4. Arquitectura

### 4.1 Archivos nuevos

- `apps/dashboard/services/__init__.py`
- `apps/dashboard/services/dashboard_service.py` — `DashboardService` con todas las agregaciones.
- `apps/dashboard/filtersets.py` — `DashboardFilter`.
- `apps/dashboard/constants.py` — metas ISO 4406, mapeos de severidad/color, defaults.
- `static/js/vendor/apexcharts/apexcharts.min.js` — librería vendorizada.
- `static/js/dashboard.js` — filtros, `fetch`, render de ApexCharts y drill-down.
- `templates/dashboard/includes/filters.html`
- `templates/dashboard/includes/kpis.html`
- `templates/dashboard/includes/tabs/*.html` — parciales por pestaña.
- `apps/dashboard/tests/__init__.py`
- `apps/dashboard/tests/test_services.py`
- `apps/dashboard/tests/test_filtersets.py`
- `apps/dashboard/tests/test_views.py`
- `apps/dashboard/tests/test_templates.py`

### 4.2 Archivos modificados

- `apps/dashboard/views.py` — `DashboardView` (login, shell) + `DashboardDataView` (JSON).
- `apps/dashboard/urls.py` — ruta `data/` (`name="data"`).
- `templates/dashboard/index.html` — reescritura completa.
- `locale/es/LC_MESSAGES/django.po` y `locale/en/LC_MESSAGES/django.po` — nuevas cadenas.

### 4.3 Sin cambios

- `apps/dashboard/models.py` permanece vacío (no se requiere modelo propio).
- `apps/dashboard/admin.py`, `apps.py`.

## 5. Capa de negocio — `DashboardService`

### 5.1 Entrada

Filtros validados con `DashboardFilter`: `year`, `fleet`, `machine`, `component_type`.

```python
@dataclass(frozen=True)
class DashboardFilters:
    year: int | None = None
    fleet_id: int | None = None
    machine_id: int | None = None
    component_type_id: int | None = None
```

### 5.2 Querysets base

- Muestras: `Report.objects.filter(is_active=True)`.
- Alertas: `Alert.objects.all()`.

Los filtros se aplican por igual a ambos, vía `machine__fleet_id`, `machine_id`,
`component__type_id` y `sample_date__year` / `detected_at__year`.

### 5.3 Métricas (`build_context(...) -> dict`)

- **KPIs**: `total`, `normal`, `caution`, `critical`, `non_conformance_rate`.
- **`condition_distribution`**: conteo por `condition` (Normal/Precaución/Alerta).
- **`samples_by_month`**: serie mensual truncada de `sample_date` con `total`, `alerts`,
  `cautions`.
- **`alerts_by_fleet`**: barras horizontales de alertas agrupadas por `machine__fleet`
  (`"Sin flota"` cuando es nulo).
- **`alerts_over_time`**: serie mensual de `alerts` vs `cautions` por `detected_at`.
- **`iso4406`**: parseo de `LabAnalysis.particle_count_iso` (`X/Y/Z`), conteo por código y
  color según meta `≤22/20/17`.
- **`range`**: `{min, max}` de `sample_date`; **`total`**: conteo de muestras.

### 5.4 Opciones de filtros (`get_filter_options()`)

Años distintos de `sample_date`, flotas activas, equipos activos y tipos de componente activos.

### 5.5 Consultas eficientes

`select_related("machine", "machine__fleet", "component", "component__type", "analysis")`
y agregaciones en base de datos (evitar N+1 y filtrado en Python).

## 6. Vistas y URLs

- `DashboardView(LoginRequiredMixin, CacheMixin, TemplateView)` — `template_name = "dashboard/index.html"`,
  `cache_timeout = 60`. Entrega opciones de filtros, datos iniciales y `last_updated`.
- `DashboardDataView(LoginRequiredMixin, View)` — `GET`, responde `JsonResponse` con el
  contrato de datos; sin caché.
- `urlpatterns`: `path("", DashboardView.as_view(), name="index")` y
  `path("data/", DashboardDataView.as_view(), name="data")`.

### 6.1 Contrato JSON

```json
{
  "kpis": {"total": 457, "normal": 280, "caution": 72, "critical": 105, "non_conformance_rate": 38.7},
  "condition_distribution": {"normal": 280, "caution": 72, "critical": 105},
  "samples_by_month": {"categories": ["2023-01"], "total": [12], "alerts": [3], "cautions": [2]},
  "alerts_by_fleet": {"categories": ["Conveyor"], "values": [80]},
  "alerts_over_time": {"categories": ["2023-01"], "alerts": [3], "cautions": [2]},
  "iso4406": {"categories": ["21/19/15"], "values": [13], "status": ["normal"]},
  "range": {"min": "2023-01-01", "max": "2026-02-28"},
  "total": 457
}
```

## 7. Frontend

- Mantener el sistema de diseño existente (TailAdmin + Outfit + tokens de color).
- **Ancla de diferenciación:** riel de severidad de color en cada KPI + dona interactiva.
- **Barra de filtros**: Año, Flota, Equipo, Componente, botón Reset, contador de muestras y
  chip de rango.
- **5 KPIs**: Total Muestras, Estado Normal, Precaución, Alerta, Tasa No Conform.
- **Gráficos ApexCharts**: dona (distribución), línea (muestras/mes), barras horizontales
  (alertas por flota), línea (alertas en el tiempo), barras (ISO 4406).
- **Pestañas**: Resumen (completa), Tendencias, Desgaste, Contaminación, Estado Aceite,
  Alertas (enlace al listado existente), Tabla Datos (tabla real, filtrada en cliente),
  Referencias (leyenda ISO y umbrales).
- **Drill-down**: clic en segmento/barra/punto → cambia a `Tabla Datos` con el filtro aplicado.
- Modo oscuro, tooltips y `aria-label`; el color nunca es el único indicador.

## 8. Acceso, caché e i18n

- `LoginRequiredMixin` en ambas vistas.
- `CacheMixin` (60 s por usuario) en el shell; endpoint JSON sin caché.
- Cadenas en `{% trans %}`; actualizar catálogos `locale/es` y `locale/en`.

## 9. Pruebas (meta 85 %)

- `test_services.py`: KPIs, distribución, series mensuales, alertas por flota, parseo ISO 4406,
  combinaciones de filtros y dataset vacío.
- `test_filtersets.py`: filtrado por año/flota/equipo/componente.
- `test_views.py`: anónimo→302; logueado→200; JSON con claves esperadas; filtros aplicados;
  `assertNumQueries` para evitar N+1; template usado.
- `test_templates.py`: presencia de KPIs/pestañas/etiquetas y ausencia de datos placeholder.

## 10. Limpieza de código sin uso

- Eliminar KPIs ficticios, "Welcome Section" y grid duplicado de módulos de equipo del
  `index.html`.
- Eliminar imports/contexto muertos en `views.py`.
- Revisar CSS/JS huérfanos tras la reescritura.

## 11. Opciones adicionales consideradas (fuera del alcance actual)

1. Comparación de período actual vs anterior (delta % en KPIs).
2. Filtro por rango de fechas y atajo "últimos 12 meses".
3. Exportar Dashboard/Tabla Datos a Excel reutilizando `ReportExportService`.
4. Vistas/filtros guardados por usuario (`DashboardPreference`).
5. Alertas en vivo (polling/SSE) y badge de críticas.
6. Metas ISO configurables vía `django-constance`.
7. Drill-down a detalle de equipo/muestra.

## 12. Validación

- Ejecutar la suite de `apps/dashboard` y el linter (`ruff`).
- Revisar el código generado con la skill `django-reviewer`.
- Verificación manual del dashboard en navegador (filtros, gráficos, pestañas, drill-down).
