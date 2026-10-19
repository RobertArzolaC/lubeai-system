# Corrección de la pestaña Tendencias en Análisis de Componente — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Hacer que la pestaña **Tendencias** muestre siempre sus gráficas: aditivos para cualquier tipo de componente y correlación uso–desgaste aun cuando los informes solo tengan horas/km de máquina.

**Architecture:** Se elimina una condición frágil del JavaScript inline que ocultaba la sección de aditivos comparando el nombre completo del tipo (`"MOTOR PRINCIPAL"`) contra `"MOTOR"`. En el servicio se añade un fallback de `lubricant_hours`/`lubricant_kms` a `machine_hours`/`machine_kms` para que la correlación funcione con datos históricos incompletos. Sin migraciones.

**Tech Stack:** Django 5, ApexCharts, JavaScript inline en plantilla, `TenantSchemaTestCase` y factorías.

**Spec:** Este documento (corrección acordada en conversación).

## Diagnóstico

- El API devuelve 4 series de aditivos con 36 puntos para Bomba, Compresor y Motor.
- `updateSectionVisibility()` ocultaba `#additives-section` porque `component_type_key` es el nombre completo (`"BOMBA CENTRÍFUGA"`, `"MOTOR PRINCIPAL"`, etc.) y la condición era `['MOTOR', '']`.
- `get_usage_correlation()` devuelve 0 puntos porque `lubricant_hours`/`lubricant_kms` están en `NULL` en los informes sembrados; `machine_hours` sí está poblado.
- Las gráficas de pestañas ocultas se redimensionan correctamente al activar la pestaña (verificado con la pestaña Desgaste).

## Global Constraints

- No ocultar la pestaña Tendencias ni la sección de aditivos por tipo de componente.
- Mantener el comportamiento actual cuando `lubricant_hours`/`lubricant_kms` sí tienen valor.
- Añadir anotaciones de tipo y docstrings en inglés; textos de interfaz con `gettext`.
- No modificar datos ni crear migraciones.

## Review Focus

- Un informe con `lubricant_hours = NULL` y `machine_hours` poblado debe producir un punto en la correlación.
- Un informe con `lubricant_hours` debe seguir usando ese valor, no las horas de máquina.
- La sección de aditivos no debe volver a ocultarse por el nombre del tipo de componente.
- La pestaña Tendencias debe renderizar sus gráficas al activarse, no solo al cargar la página.
- Un componente sin datos de correlación debe mostrar el mensaje “No hay datos…”, no un contenedor vacío.

---

### Task 1: Fallback de uso en la correlación

**Files:**
- Modify: `apps/reports/services/component_analysis.py:551-598`
- Test: `apps/reports/tests/test_services.py`

**Interfaces:**
- `ComponentAnalysisService.get_usage_correlation() -> dict[str, Any]` mantiene su contrato.
- `series[0].data[i].x` usa `lubricant_hours` o, si es `NULL`, `machine_hours`; análogamente para km.

- [x] **Step 1: Escribir tests que fallen**

En `apps/reports/tests/test_services.py`, agregar una clase
`ComponentAnalysisUsageCorrelationTests(TenantSchemaTestCase)` con:

```python
def test_uses_lubricant_hours_when_present(self) -> None:
    """The correlation prefers the lubricant hours over machine hours."""

def test_falls_back_to_machine_hours(self) -> None:
    """Missing lubricant hours fall back to machine hours."""

def test_falls_back_to_machine_kms(self) -> None:
    """Missing lubricant kilometres fall back to machine kilometres."""
```

Cada test crea una máquina, un componente, un informe y un `LabAnalysis` con
`iron_fe`, invoca `ComponentAnalysisService(component.pk).get_usage_correlation()`
y compara `series[0].data[0]["x"]` con el valor esperado.

- [x] **Step 2: Ejecutar y verificar que fallan**

Run: `python manage.py test apps.reports.tests.test_services.ComponentAnalysisUsageCorrelationTests`
Expected: FAIL en los casos de fallback porque `x` queda vacío.

- [x] **Step 3: Implementar el fallback**

En `get_usage_correlation()`:

```python
if measurement_unit == "hours":
    usage = report.lubricant_hours
    if usage is None:
        usage = report.machine_hours
    usage_label = "Horas"
else:
    usage = report.lubricant_kms
    if usage is None:
        usage = report.machine_kms
    usage_label = "Kilómetros"
```

Mantener el `continue` cuando ambos sean `None`.

- [x] **Step 4: Ejecutar y verificar**

Run: `python manage.py test apps.reports.tests.test_services.ComponentAnalysisUsageCorrelationTests`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/reports/services/component_analysis.py apps/reports/tests/test_services.py
git commit -m "fix(reports): fall back to machine usage in correlation chart"
```

### Task 2: Mostrar siempre la tendencia de aditivos

**Files:**
- Modify: `templates/reports/report/component_analysis.html:856-863` y llamada en `:465`
- Test: `apps/reports/tests/test_templates.py`

**Interfaces:**
- `#additives-section` permanece visible para todos los tipos.
- Se elimina `currentComponentTypeKey` si queda sin uso.

- [x] **Step 1: Escribir test que falle**

En `apps/reports/tests/test_templates.py`, agregar un `SimpleTestCase` que lea
`templates/reports/report/component_analysis.html` y verifique:

```python
self.assertNotIn("showAdditives", content)
self.assertNotIn("['MOTOR', '']", content)
```

- [x] **Step 2: Ejecutar y verificar que falla**

Run: `python manage.py test apps.reports.tests.test_templates`
Expected: FAIL porque la condición sigue presente.

- [x] **Step 3: Implementar**

Eliminar `updateSectionVisibility()` y su llamada, junto con la variable
`currentComponentTypeKey` y sus asignaciones si quedan sin uso. La sección de
aditivos queda visible siempre.

- [x] **Step 4: Ejecutar y verificar**

Run: `python manage.py test apps.reports.tests.test_templates`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add templates/reports/report/component_analysis.html apps/reports/tests/test_templates.py
git commit -m "fix(reports): always show additive trends section"
```

### Task 3: Verificación final

- [x] **Step 1: Suite relevante**

Run: `python manage.py test apps.reports`
Expected: OK (salvo fallos preexistentes documentados).

- [x] **Step 2: Verificación en navegador**

Con un componente Bomba y otro Motor:
- Abrir la pestaña Tendencias.
- Comprobar la gráfica de aditivos (4 series) y la correlación con 36 puntos.
- Cambiar entre modo claro/oscuro.
- Confirmar que la pestaña Desgaste sigue renderizando.

---

## Estado de implementación

Implementado el 2026-10-19.

- `apps/reports/services/component_analysis.py`: la correlación usa
  `lubricant_hours`/`lubricant_kms` y hace fallback a `machine_hours`/`machine_kms`.
- `templates/reports/report/component_analysis.html`: se eliminó la condición que
  ocultaba la sección de aditivos; la pestaña Tendencias muestra aditivos para
  cualquier tipo de componente.
- Tests agregados en `apps/reports/tests/test_services.py` y
  `apps/reports/tests/test_templates.py`.

Verificación:

- `python manage.py test apps.reports`: 117/117 OK.
- Navegador (Playwright) con datos de `marco`:
  - Bomba Centrífuga: aditivos con 4 series y correlación con 36 puntos.
  - Motor Principal: aditivos con 4 series y correlación con 36 puntos.
  - Pestaña Desgaste: sigue mostrando sus 3 series.
  - Modo claro y oscuro sin errores de consola.
- `ruff check`: OK.
