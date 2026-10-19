# Búsqueda en filtros de Máquina y Componente del Dashboard — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reemplazar los selects planos de Máquina y Componente del dashboard por selects con búsqueda en servidor, mostrando solo los componentes de la máquina seleccionada.

**Architecture:** Se reutiliza la infraestructura Select2 + Django Autocomplete Light ya usada en Análisis de Componente (`apps/core/widgets.py`, `apps/equipment/autocomplete.py`). El `DashboardFilter` declara los widgets con endpoints AJAX; el filtro de componente reemplaza al filtro por tipo de componente y se valida contra la máquina elegida. La plantilla renderiza el formulario del filterset y `dashboard.js` sincroniza Select2 con el refresco AJAX existente.

**Tech Stack:** Django 5, django-filter, django-autocomplete-light (Select2), Tailwind/TailAdmin, JavaScript vanilla.

**Spec:** Este mismo documento (cambio acotado acordado en conversación).

## Global Constraints

- Código, nombres y docstrings en inglés; textos de interfaz traducibles con `gettext_lazy`.
- Sin migraciones ni cambios de modelos.
- Todas las funciones y tests con anotaciones de tipo y docstrings (PEP 257).
- Reutilizar `apps/core/widgets.ThemeModelSelect2` y `static/css/select2-custom.css`.
- Los endpoints de autocompletado respetan el alcance de organizaciones del usuario (`apps/organizations/scoping.py`).
- Tests con `django.test.TestCase`/`TenantSchemaTestCase` y factorías existentes.

## Review Focus

- Un componente enviado sin máquina, o de otra máquina, no debe filtrar ni romper: debe producir un filterset inválido (HTTP 400 en el endpoint de datos).
- Cambiar o limpiar la máquina debe limpiar el componente para no dejar una selección inconsistente.
- El botón Reset debe limpiar también la selección visible de Select2 y hacer un solo refresco.
- El modo oscuro y el ancho de los selects deben conservar el estilo TailAdmin.
- Si JavaScript falla, el resto del dashboard no debe quedar inutilizable.

---

### Task 1: Filtro por componente con búsqueda en servidor

**Files:**
- Modify: `apps/dashboard/filtersets.py`
- Modify: `apps/dashboard/services/dashboard_service.py`
- Modify: `apps/dashboard/views.py`
- Test: `apps/dashboard/tests/test_filtersets.py`
- Test: `apps/dashboard/tests/test_services.py`
- Test: `apps/dashboard/tests/test_views.py`

**Interfaces:**
- `DashboardFilter` expone `machine` y `component` como `ModelChoiceFilter` con `ThemeModelSelect2`.
- `DashboardFilters(component_id: int | None = None)`.
- `DashboardService.get_filters_key()` incluye `component_id`.
- `DashboardView` agrega `filter_form` al contexto.

- [x] **Step 1: Escribir tests que fallen**

En `test_filtersets.py`, reemplazar el caso de tipo de componente por:
`test_filter_by_component`, `test_component_requires_machine` (`is_valid()` falso) y
`test_component_from_other_machine_is_invalid` (`is_valid()` falso).
En `test_services.py`, reemplazar `test_filter_by_component_type` por
`test_filter_by_component` usando `DashboardFilters(component_id=...)`.
En `test_views.py`, agregar `test_data_applies_machine_and_component_filters` y
`test_data_rejects_component_without_machine` (400).

- [x] **Step 2: Ejecutar los tests y verificar que fallan**

Run: `python manage.py test apps.dashboard.tests.test_filtersets apps.dashboard.tests.test_services apps.dashboard.tests.test_views`
Expected: FAIL por `component_type` inexistente.

- [x] **Step 3: Implementar el filtro**

En `filtersets.py`:
- `machine` con `ThemeModelSelect2(url="apps.equipment:autocomplete_machine")`.
- `component` con `ThemeModelSelect2(url="apps.equipment:autocomplete_component", forward=["machine"])`.
- Eliminar `component_type` de campos y de `scope_choices`.
- En `__init__`, tras `scope_choices`, limitar el queryset de `component` a `machine_id` cuando el filterset está bound; sin máquina o con máquina inválida, `none()`.

En `dashboard_service.py`:
- Renombrar `component_type_id` a `component_id`.
- Filtrar reportes y alertas con `component_id=...`.
- Actualizar `get_filters_key`.
- Quitar `machines` y `component_types` de `get_filter_options` (ya no se renderizan; evita exponer tipos sin alcance).

En `views.py`:
- `DashboardView.get_context_data` agrega `context["filter_form"] = filtersets.DashboardFilter(request=request).form`.
- `DashboardDataView` construye `component_id=cleaned["component"].pk if cleaned.get("component") else None`.

- [x] **Step 4: Ejecutar los tests y verificar que pasan**

Run: `python manage.py test apps.dashboard`
Expected: OK.

- [x] **Step 5: Commit**

```bash
git add apps/dashboard
git commit -m "feat(dashboard): filter by machine component with server-side search"
```

### Task 2: Renderizar Select2 en la barra de filtros

**Files:**
- Modify: `templates/dashboard/includes/filters.html`
- Modify: `templates/dashboard/index.html`
- Test: `apps/dashboard/tests/test_templates.py`
- Test: `apps/dashboard/tests/test_views.py`

**Interfaces:**
- `filters.html` consume `filter_form.machine` y `filter_form.component`.
- `index.html` carga `{{ filter_form.media }}` y `static/css/select2-custom.css`.

- [x] **Step 1: Escribir tests que fallen**

En `test_templates.py`, agregar `test_filters_render_autocomplete_fields` verificando
`filter_form.machine` y `filter_form.component` en el template.
En `test_views.py`, ampliar `test_index_renders_for_logged_user` para comprobar
`select2` y `admin/js/vendor/jquery` en el HTML renderizado.

- [x] **Step 2: Ejecutar y verificar fallo**

Run: `python manage.py test apps.dashboard.tests.test_templates apps.dashboard.tests.test_views`
Expected: FAIL.

- [x] **Step 3: Implementar la plantilla**

Reemplazar los `<select>` de Máquina y Componente por los widgets del formulario.
Aplicar la clase compartida `filter-control` a buscador, año y flota (con anchos
`sm:w-80`, `sm:w-32`, `sm:w-48` y `sm:w-64` para máquina/componente). Mantener el
bloque `extra_css` en `index.html` con `select2-custom.css` y `dashboard-filters.css`.

- [x] **Step 4: Ejecutar y verificar**

Run: `python manage.py test apps.dashboard`
Expected: OK.

- [x] **Step 5: Commit**

```bash
git add templates/dashboard apps/dashboard/tests
git commit -m "feat(dashboard): render searchable machine and component filters"
```

### Task 3: Sincronizar la interacción con el refresco AJAX

**Files:**
- Modify: `static/js/dashboard.js`

**Interfaces:**
- `setupFilters()` limpia `component` al cambiar `machine`.
- El reset sincroniza Select2 con `change.select2` y refresca una sola vez.

- [x] **Step 1: Implementar**

Agregar un helper `clearField(field)` que ponga `value=""` y, si jQuery/Select2
están disponibles, ejecute `.val(null).trigger("change.select2")`.
Registrar el cambio de `machine` con jQuery (`jquery(machine).on("change", ...)`)
porque Select2 emite `change` a través de jQuery, no como evento nativo; de lo
contrario no se limpia el componente ni se refresca el panel. Reutilizar el helper
en el reset.

- [x] **Step 2: Verificar sintaxis**

Run: `node --check static/js/dashboard.js`
Expected: sin salida (OK).

- [x] **Step 3: Commit**

```bash
git add static/js/dashboard.js
git commit -m "feat(dashboard): keep select2 filters in sync with ajax refresh"
```

### Task 4: Verificación final

- [x] **Step 1: Ejecutar la suite relevante**

Run: `python manage.py test apps.dashboard apps.equipment.tests.test_autocomplete`
Expected: OK.

- [x] **Step 2: Revisar el diff**

Run: `git diff --check && git status --short`
Expected: sin errores de whitespace.

- [x] **Step 3: Prueba manual**

Abrir `/dashboard/`, buscar una máquina por nombre/serie, elegirla, comprobar que
Componente solo lista sus componentes, cambiar de máquina, usar Reset y verificar
modo oscuro y ancho móvil.

### Task 5: Unificar el diseño de todos los inputs

**Files:**
- Create: `static/css/dashboard-filters.css`
- Modify: `templates/dashboard/includes/filters.html`
- Modify: `templates/dashboard/index.html`
- Modify: `apps/dashboard/filtersets.py`
- Test: `apps/dashboard/tests/test_templates.py`

**Interfaces:**
- Todos los controles de la barra comparten `filter-control` y la misma altura,
  borde, radio, tipografía y foco; Select2 se normaliza con reglas bajo
  `#dashboard-filters`.

- [x] **Step 1: Definir el sistema visual** — altura 2.75rem, padding 0 0.75rem,
  borde 1px `--color-stroke`, radio 0.5rem, fuente 0.875rem, fondo transparente y
  foco con `--color-primary`. Incluir el selector de año/flota con flecha SVG y el
  campo de búsqueda del desplegable Select2.

- [x] **Step 2: Verificar en navegador** — medir con Playwright los cuatro controles
  en claro y oscuro (altura 44px, fuente 14px, radio 8px, mismo borde) y comprobar
  búsqueda de máquina, filtrado de componentes, limpieza al cambiar máquina y reset.

- [x] **Step 3: Commit**

```bash
git add static/css/dashboard-filters.css templates/dashboard apps/dashboard/filtersets.py apps/dashboard/tests/test_templates.py
git commit -m "style(dashboard): unify filter control design"
```

---

## Estado de implementación (2026-10-19)

Tasks 1 a 5 implementadas:

- `apps/dashboard/filtersets.py`: widgets Select2 para `machine` y `component`, validación
  componente↔máquina y clase compartida `filter-control`.
- `apps/dashboard/services/dashboard_service.py`: `component_id` en filtros, reportes,
  alertas y clave de caché; opciones estáticas reducidas a años y flotas.
- `apps/dashboard/views.py`: `filter_form` en el contexto y `component` en el endpoint.
- `templates/dashboard/{index.html,includes/filters.html}`: render de los widgets, clase
  `filter-control` en buscador/año/flota y carga de `select2-custom.css` y
  `dashboard-filters.css`.
- `static/css/dashboard-filters.css`: altura, borde, radio, tipografía, foco y flecha
  unificados para controles nativos y Select2 (incluido el buscador del desplegable).
- `static/js/dashboard.js`: cambio de máquina enlazado por jQuery (Select2 no emite
  eventos nativos), limpieza del componente y reset sincronizado con Select2.
- Tests actualizados/agregados en `apps/dashboard/tests/`.

Verificación:

- `python manage.py test apps.dashboard apps.equipment.tests.test_autocomplete`:
  65 de 66 tests OK.
- `test_data_query_count_is_bounded` falla con `20 != 14`; el mismo fallo se reprodujo
  sobre la rama sin estos cambios, por lo que es preexistente y ajeno a esta mejora.
- Render real del dashboard comprobado en el entorno de tests: los selects incluyen los
  endpoints `/equipment/machines/autocomplete/` y `/equipment/components/autocomplete/`,
  los assets de Select2 y los skins.
- Prueba manual con Playwright en `http://marco.localhost:8000/dashboard/`:
  alturas 44px, fuente 14px, radio 8px y mismo borde en buscador, año, máquina,
  componente y buscador del desplegable, en claro y oscuro. Se verificó búsqueda de
  máquina por nombre/serie, componentes limitados a la máquina, limpieza al cambiar de
  máquina, reset y peticiones AJAX `machine`/`component`.
- `ruff check` y `node --check static/js/dashboard.js`: OK.
- Los datos de prueba y la sesión usados en la comprobación manual fueron eliminados.

