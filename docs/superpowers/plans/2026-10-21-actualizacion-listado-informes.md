# Actualización del listado de informes — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** eliminar el filtro por estado, dejar los filtros avanzados en cascada Máquina → Componente y retirar `IsActive` de `Report` porque su ciclo de vida ya lo cubre `status`.

**Architecture:** se reutiliza el patrón de filtros dependientes ya probado en `apps/dashboard/filtersets.py`: `ThemeModelSelect2` con `forward=["machine"]`, reducción del queryset de componentes en el servidor y `{{ filter.form.media }}` en la plantilla. La eliminación de `is_active` se propaga a todos los querysets, formularios, admin, factories, dashboard, MCP y tests, con una migración que elimina el campo y sus índices.

**Tech Stack:** Django 6, django-filter, Django Autocomplete Light (Select2), Tailwind/TailAdmin, factory_boy, unittest.

**Spec:** conversación de planificación del 2026-10-21 (requisitos del listado de informes).

## Global Constraints

- Código e identificadores en inglés; respuestas, plan y documentación en español (AGENTS.md).
- Mantener el sistema visual TailAdmin/Tailwind existente; sin rediseños.
- `status` sigue existiendo en el modelo, detalle, admin, MCP y columna del Excel de exportación. Solo se quita como filtro.
- La migración elimina datos de `is_active` de `Report`; es irreversible.
- Tests con `uv run python manage.py test ... --settings=config.settings.testing`.
- Lint con `uv run ruff check` y `uv run ruff format --check`.

## Review Focus

1. Componente sin máquina: no debe mostrar todos los componentes ni aceptar combinaciones inválidas.
2. Reportes que antes tenían `is_active=False` pasan a ser visibles en dashboard, MCP y conteos.
3. El listado debe cargar jQuery/Select2/DAL; sin `media` el filtro se degrada a un `<select>` vacío.
4. La exportación no debe romper preview ni descarga al quitar el filtro de estado.
5. Laboratorio: el conteo y el detalle deben seguir contando todos los informes.

---

### Task 1: Retirar IsActive de Report

**Files:**
- Modify: `apps/reports/models.py`
- Create: `apps/reports/migrations/0004_remove_report_is_active.py`
- Modify: `apps/reports/factories.py`
- Modify: `apps/reports/forms.py`
- Modify: `apps/reports/admin.py`
- Modify: `apps/reports/views.py`
- Modify: `apps/reports/services/component_analysis.py`
- Modify: `apps/dashboard/services/dashboard_service.py`
- Modify: `apps/integrations/mcp/tools/reports.py`
- Modify: `apps/integrations/mcp/tools/equipment.py`
- Modify: `apps/integrations/mcp/tools/account.py`
- Modify: `apps/alerts/forms.py`
- Test: `apps/reports/tests/test_models.py`
- Test: `apps/reports/tests/test_forms.py`
- Test: `apps/reports/tests/test_views.py`

**Interfaces:**
- Produces: `Report` without an `is_active` field; `ReportFactory` without `is_active`.
- Consumes: none.

- [x] **Step 1: Write the failing test**

```python
def test_report_no_longer_has_is_active_field(self) -> None:
    field_names = {field.name for field in models.Report._meta.get_fields()}
    self.assertNotIn("is_active", field_names)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run python manage.py test apps.reports.tests.test_models.ReportModelTests --settings=config.settings.testing`
Expected: FAIL because `is_active` is still present.

- [x] **Step 3: Remove `core_models.IsActive` and its indexes from `Report`**

Keep `status`, `condition` and their indexes.

- [x] **Step 4: Generate the migration**

Run: `uv run python manage.py makemigrations reports --name remove_report_is_active --settings=config.settings.testing`
Expected: a migration with `RemoveField("report", "is_active")` plus index operations.

- [x] **Step 5: Update every `Report.is_active` usage**

Update factories, forms, admin, laboratory views, dashboard service, MCP tools, alerts form and component analysis service. Do not touch `is_active` on Laboratory, AnalysisThreshold, Machine, Component, Fleet, Branch or Tenant.

- [x] **Step 6: Update test payloads**

Remove `"is_active": True` from `report_payload()` in `apps/reports/tests/test_views.py` and `apps/reports/tests/test_forms.py`.

- [x] **Step 7: Run the affected suite**

Run: `uv run python manage.py test apps.reports apps.dashboard apps.integrations apps.alerts --settings=config.settings.testing`
Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add apps docs
git commit -m "refactor(reports): drop is_active from Report"
```

---

### Task 2: Quitar los filtros Estado y Registro activo

**Files:**
- Modify: `apps/reports/filtersets.py`
- Modify: `templates/reports/report/list.html`
- Modify: `templates/reports/report/export.html`
- Test: `apps/reports/tests/test_filtersets.py`
- Test: `apps/reports/tests/test_views.py`
- Test: `apps/reports/tests/test_templates.py`

**Interfaces:**
- Consumes: `Report` from Task 1 (no `is_active`).
- Produces: `ReportFilter` with only `lab_number_search`, `organization`, `laboratory`, `machine`, `component`, `condition`; `ReportExportFilter` without `status`.

- [x] **Step 1: Write the failing tests**

```python
def test_status_and_is_active_filters_removed(self) -> None:
    filterset = filtersets.ReportFilter(queryset=models.Report.objects.all())
    self.assertNotIn("status", filterset.filters)
    self.assertNotIn("is_active", filterset.filters)

def test_export_status_filter_removed(self) -> None:
    filterset = filtersets.ReportExportFilter(queryset=models.Report.objects.all())
    self.assertNotIn("status", filterset.filters)
```

Also assert the report list response has no `name="status"` / `name="is_active"` and the export page has no `id_status`.

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run python manage.py test apps.reports.tests.test_filtersets apps.reports.tests.test_views apps.reports.tests.test_templates --settings=config.settings.testing`
Expected: FAIL on the new assertions.

- [x] **Step 3: Update the filtersets**

Remove `status` and `is_active` from `ReportFilter` (declarations and `Meta.fields`). Remove `status` from `ReportExportFilter` (declaration and `Meta.fields`). Keep `condition`.

- [x] **Step 4: Update the list template**

Primary row: search 6 columns, condition 3, Apply 3. Remove the status select. In the advanced `{% with %}` remove `act`; remove the `is_active` block.

- [x] **Step 5: Update the export template**

Remove the `id_status` block.

- [x] **Step 6: Replace the old status-filter test and run the suite**

Run: `uv run python manage.py test apps.reports.tests.test_filtersets apps.reports.tests.test_views apps.reports.tests.test_templates --settings=config.settings.testing`
Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add apps/reports/filtersets.py templates/reports/report apps/reports/tests
git commit -m "feat(reports): remove status and record-status filters from lists"
```

---

### Task 3: Cascada Máquina → Componente

**Files:**
- Modify: `apps/reports/filtersets.py`
- Modify: `templates/reports/report/list.html`
- Test: `apps/reports/tests/test_filtersets.py`
- Test: `apps/reports/tests/test_views.py`

**Interfaces:**
- Consumes: `ReportFilter` from Task 2, `apps.equipment:autocomplete_machine` and `apps.equipment:autocomplete_component`.
- Produces: `ReportFilter._narrow_component_choices() -> None`, called from `__init__`.

- [x] **Step 1: Write the failing tests**

```python
def test_component_choices_are_narrowed_by_machine(self) -> None:
    machine = equipment_factories.MachineFactory()
    other_machine = equipment_factories.MachineFactory()
    component = equipment_factories.ComponentFactory(machine=machine)
    other_component = equipment_factories.ComponentFactory(machine=other_machine)
    filterset = filtersets.ReportFilter(
        {"machine": machine.pk}, queryset=models.Report.objects.all()
    )
    queryset = filterset.filters["component"].field.queryset
    self.assertIn(component, queryset)
    self.assertNotIn(other_component, queryset)

def test_component_choices_empty_without_machine(self) -> None:
    filterset = filtersets.ReportFilter({}, queryset=models.Report.objects.all())
    self.assertFalse(filterset.filters["component"].field.queryset.exists())
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run python manage.py test apps.reports.tests.test_filtersets.ReportFilterTests --settings=config.settings.testing`
Expected: FAIL because component choices are not narrowed.

- [x] **Step 3: Implement the cascade**

Add `ThemeModelSelect2` widgets with `forward=["machine"]` on `component`, then call `_narrow_component_choices()` after `scoping.scope_choices` in `ReportFilter.__init__`.

- [x] **Step 4: Wire the template**

Add `{% block extra_css %}{{ filter.form.media }}<link rel="stylesheet" href="{% static 'css/select2-custom.css' %}">{% endblock %}` and render `{{ filter.form.machine }}` / `{{ filter.form.component }}`. Add a minimal JS handler that clears the component when the machine changes.

- [x] **Step 5: Run the suite**

Run: `uv run python manage.py test apps.reports.tests.test_filtersets apps.reports.tests.test_views apps.equipment.tests.test_autocomplete --settings=config.settings.testing`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add apps/reports/filtersets.py templates/reports/report/list.html apps/reports/tests
git commit -m "feat(reports): cascade machine and component filters"
```

---

### Task 4: Validación final con django-reviewer

**Files:**
- Review: `git diff` against the branch base.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: a reviewed, green branch.

- [x] **Step 1: Run project checks**

Run: `uv run python manage.py check --settings=config.settings.testing`
Expected: `System check identified no issues`.

- [x] **Step 2: Run lint and formatting**

Run: `uv run ruff check apps/reports apps/dashboard apps/integrations apps/alerts`
Expected: no errors.

Run: `uv run ruff format --check apps/reports apps/dashboard apps/integrations apps/alerts`
Expected: no reformat needed.

- [x] **Step 3: Run the full affected suite**

Run: `uv run python manage.py test apps.reports apps.dashboard apps.integrations apps.alerts apps.tenancy --settings=config.settings.testing`
Expected: PASS.

- [x] **Step 4: Apply django-reviewer to the diff**

Review scoping, N+1 queries, component/machine validation and project conventions. Fix only findings inside the scope, then rerun Step 3.

- [x] **Step 5: Commit review fixes if any**

```bash
git add -A
git commit -m "chore(reports): address review findings"
```
