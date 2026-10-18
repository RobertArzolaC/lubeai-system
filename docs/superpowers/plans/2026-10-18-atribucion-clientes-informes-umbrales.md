# Atribución de clientes en Informes y Umbrales — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar la columna y el filtro "Cliente" en los listados de Informes y Umbrales cuando el usuario pertenece a un nodo del árbol con descendientes.

**Architecture:** Se reutiliza el patrón de atribución de clientes de Equipos: `ClientAttributionMixin` para el join y la bandera `show_organization`, y `scope_organization_filter` para el filtro. Se agrega `include_self=False` a los helpers de scoping para que el select liste solo descendientes. Umbrales deriva su organización de `component_type.organization` y su listado se scopea a ese path, conservando los umbrales globales.

**Tech Stack:** Django 6.0, django-filter, Django templates + Tailwind, factory_boy, Django `TestCase`.

**Spec:** `docs/superpowers/specs/2026-10-17-atribucion-clientes-equipos-design.md` (patrón base) y las decisiones de esta sesión (abajo).

## Decisiones de esta sesión

| Tema | Decisión |
|---|---|
| Predicado | `scoping.can_choose_organization(user)`: un nodo padre (subárbol > 1) ve columna y filtro; una hoja no; superusuario/plataforma/sin organización sí. |
| Filtro | Lista solo descendientes estrictos (`include_self=False`), sin la organización propia. |
| Informes | `Report.organization` es una FK directa. |
| Umbrales | Organización derivada de `component_type.organization`; los globales (`component_type = null`) siguen visibles para todos y muestran "—" en la columna. |
| Listado de Umbrales | Se scopea por `component_type__organization` más los globales (hoy no está scopeado). |
| Fuera de alcance | Exportación de Informes; detalle/edición/borrado de Umbrales; migraciones. |

## Global Constraints

- Código, comentarios y docstrings en inglés (AGENTS.md).
- UI en español vía `{% trans %}` / `_()`; reutilizar "Client" y "All Clients".
- Type annotations en funciones y tests; docstrings PEP 257.
- Tests con Django `TestCase` y factories de la app.
- Sin migraciones.
- No romper Equipos/Usuarios/Alertas: los defaults de scoping quedan en `include_self=True`.

## Review Focus

- Usuario hoja: no debe ver ni el select ni la columna "Cliente" en ninguna de las dos pantallas.
- Usuario padre: el select no debe incluir su propia organización, solo descendientes.
- Umbrales globales (`component_type = null`): deben seguir visibles para usuarios con organización y mostrar "—".
- Umbrales de otra organización: no deben aparecer en el listado ni poder filtrarse.
- Informes sin organización: columna "—" y el render no debe romperse.

---

### Task 1: `include_self` en los helpers de scoping

**Files:**
- Modify: `apps/organizations/scoping.py`
- Test: `apps/organizations/tests/test_scoping.py`

**Interfaces:**
- Produces: `visible_organizations(user, *, include_self: bool = True) -> QuerySet`
- Produces: `scope_organization_filter(filterset, name: str = "organization", *, include_self: bool = True) -> None`

- [ ] **Step 1: Write the failing tests**

Agregar en `apps/organizations/tests/test_scoping.py`:

```python
class VisibleOrganizationsStrictChildrenTests(TestCase):
    """``include_self=False`` excludes the user's own organization."""

    def setUp(self) -> None:
        self.lab = factories.OrganizationFactory(
            slug="vc-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = factories.OrganizationFactory(
            slug="vc-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )

    def _user_for(self, organization):
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        return user

    def test_exclude_self_returns_only_descendants(self) -> None:
        user = self._user_for(self.lab)
        ids = set(
            scoping.visible_organizations(user, include_self=False).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(ids, {self.final.id})

    def test_include_self_keeps_own_organization(self) -> None:
        user = self._user_for(self.lab)
        ids = set(
            scoping.visible_organizations(user, include_self=True).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(ids, {self.lab.id, self.final.id})

    def test_exclude_self_leaf_returns_nothing(self) -> None:
        user = self._user_for(self.final)
        self.assertFalse(
            scoping.visible_organizations(user, include_self=False).exists()
        )

    def test_exclude_self_unrestricted_returns_all(self) -> None:
        # The test database also contains the MARCO organization seeded by
        # migration 0002_seed_marco_tenant, so compare against the full table.
        user = user_factories.UserFactory()
        ids = set(
            scoping.visible_organizations(user, include_self=False).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(
            ids,
            set(organization_models.Organization.objects.values_list("id", flat=True)),
        )
        self.assertIn(self.lab.id, ids)
        self.assertIn(self.final.id, ids)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.organizations.tests.test_scoping.VisibleOrganizationsStrictChildrenTests -v 2`
Expected: FAIL with `TypeError: visible_organizations() got an unexpected keyword argument 'include_self'`.

- [ ] **Step 3: Implement the parameter in `apps/organizations/scoping.py`**

```python
def visible_organizations(user, *, include_self: bool = True) -> QuerySet:
    """Return the organizations ``user`` may act upon."""
    from apps.organizations import models as organization_models

    queryset = organization_models.Organization.objects.all()
    visible_ids = user_visible_organization_ids(user)
    if visible_ids is None:
        return queryset
    if not include_self:
        organization = getattr(user, "organization", None)
        if organization is None:
            return queryset.none()
        descendant_ids = organization.descendants(include_self=False).values_list(
            "id", flat=True
        )
        return queryset.filter(pk__in=descendant_ids)
    return queryset.filter(pk__in=visible_ids)
```

Y propagar el parámetro:

```python
def scope_organization_filter(
    filterset, name: str = "organization", *, include_self: bool = True
) -> None:
    ...
    filterset.filters[name].queryset = visible_organizations(
        request.user, include_self=include_self
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.organizations.tests.test_scoping -v 2`
Expected: PASS.

---

### Task 2: `client_organization_path` en `ClientAttributionMixin`

**Files:**
- Modify: `apps/core/mixins/views.py`
- Test: `apps/core/tests/test_mixins_views.py`

**Interfaces:**
- Produces: `ClientAttributionMixin.client_organization_path: ClassVar[str] = "organization"`

- [ ] **Step 1: Write the failing test**

Agregar en `apps/core/tests/test_mixins_views.py`:

```python
class CustomClientPathListView(core_mixins.ClientAttributionMixin, core_mixins.BaseListView):
    """List view with a nested client attribution path."""

    model = equipment_models.Machine
    permission_required = "equipment.view_machine"
    client_organization_path = "fleet__organization"


class ClientAttributionMixinTests(TestCase):
    """The mixin joins the configured client path."""

    def test_default_path_joins_organization(self) -> None:
        view = ListTestView()
        related = view.get_queryset().query.select_related
        self.assertIn("organization", related)

    def test_custom_path_joins_nested_organization(self) -> None:
        view = CustomClientPathListView()
        related = view.get_queryset().query.select_related
        self.assertIn("fleet", related)
        self.assertIn("organization", related["fleet"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.core.tests.test_mixins_views.ClientAttributionMixinTests -v 2`
Expected: FAIL (`AttributeError` or the nested path is missing).

- [ ] **Step 3: Implement the attribute**

```python
class ClientAttributionMixin:
    """Expose the owning organization in tenant-scoped list views."""

    client_organization_path: ClassVar[str] = "organization"

    def get_queryset(self) -> QuerySet:
        """Return the list queryset with the owning organization joined."""
        return super().get_queryset().select_related(self.client_organization_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.core.tests.test_mixins_views -v 2`
Expected: PASS.

---

### Task 3: Informes — columna y filtro

**Files:**
- Modify: `apps/reports/views.py` (`ReportListView`)
- Modify: `apps/reports/filtersets.py` (`ReportFilter`)
- Modify: `templates/reports/report/list.html`
- Test: `apps/reports/tests/test_client_attribution.py` (new)

**Interfaces:**
- Consumes: `ClientAttributionMixin` (Task 2), `scope_organization_filter(..., include_self=False)` (Task 1).
- Produces: `ReportFilter.organization` (declared `ModelChoiceFilter`).

- [ ] **Step 1: Write the failing tests**

Crear `apps/reports/tests/test_client_attribution.py` con:

```python
"""Tests for client attribution on the report and threshold lists."""

from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.equipment import factories as equipment_factories
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.reports import factories, filtersets, models
from apps.reports import views as report_views
from apps.users import factories as user_factories
from apps.users import models as user_models


def user_for(organization: organization_models.Organization) -> user_models.User:
    """Return a persisted user belonging to ``organization``."""
    user = user_factories.UserFactory()
    user.organization = organization
    user.save(update_fields=["organization"])
    return user


def grant_permissions(user: user_models.User, *codenames: str) -> None:
    """Grant the given reports permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="reports", codename__in=codenames
    )
    user.user_permissions.add(*permissions)


def list_context(view_class, user: user_models.User) -> dict:
    """Return the context of ``view_class`` for ``user``."""
    request = RequestFactory().get("/")
    request.user = user
    view = view_class()
    view.request = request
    view.kwargs = {}
    view.object_list = view.get_queryset()
    return view.get_context_data()


class ReportClientAttributionTests(TestCase):
    """Client attribution for the report list."""

    def setUp(self) -> None:
        self.lab = organization_factories.OrganizationFactory(
            slug="ra-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="ra-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.lab_user = user_for(self.lab)
        self.final_user = user_for(self.final)

    def test_show_organization_true_for_parent(self) -> None:
        self.assertTrue(list_context(report_views.ReportListView, self.lab_user)["show_organization"])

    def test_show_organization_false_for_leaf(self) -> None:
        self.assertFalse(list_context(report_views.ReportListView, self.final_user)["show_organization"])

    def test_organization_filter_lists_strict_children(self) -> None:
        filterset = filtersets.ReportFilter(
            queryset=models.Report.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(filterset.filters["organization"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.final.id})

    def test_filter_by_organization(self) -> None:
        report_lab = factories.ReportFactory(organization=self.lab)
        report_final = factories.ReportFactory(organization=self.final)
        filterset = filtersets.ReportFilter(
            {"organization": self.final.pk},
            queryset=models.Report.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(filterset.qs.values_list("id", flat=True))
        self.assertEqual(ids, {report_final.id})
        self.assertNotIn(report_lab.id, ids)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.reports.tests.test_client_attribution.ReportClientAttributionTests -v 2`
Expected: FAIL (`KeyError: 'organization'` / `show_organization` missing).

- [ ] **Step 3: Implement the view and filter**

En `apps/reports/views.py`:

```python
class ReportListView(core_mixins.ClientAttributionMixin, core_mixins.BaseListView):
    ...
```

En `apps/reports/filtersets.py`, dentro de `ReportFilter`:

```python
organization = django_filters.ModelChoiceFilter(
    queryset=organization_models.Organization.objects.all(),
    empty_label=_("All Clients"),
    label=_("Client"),
)
```

Agregar `"organization"` a `Meta.fields` y, en `__init__`:

```python
scoping.scope_organization_filter(self, include_self=False)
```

Importar `from apps.organizations import models as organization_models`.

- [ ] **Step 4: Update the template**

En `templates/reports/report/list.html`:

1. En el bloque de filtros avanzados, agregar condicionado por `{% if show_organization %}`:

```html
<div class="md:col-span-3">
    <label for="id_organization" class="mb-2.5 block text-xs font-bold uppercase tracking-wider text-bodydark2">{{ filter.form.organization.label }}</label>
    {% render_field filter.form.organization class="w-full rounded-xl border border-stroke bg-white py-3 px-4 text-sm font-semibold text-black outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/5 dark:border-form-strokedark dark:bg-meta-4 dark:text-white" %}
</div>
```

2. Incluir `org=filter.form.organization.value` en el `{% with %}` del bloque avanzado y sumarlo a la condición `open` y al punto indicador.

3. En el encabezado y en cada fila, agregar la celda "Cliente" condicionada por `show_organization`, con badge:

```html
{% if show_organization %}
<div class="col-span-2 flex items-center">
    {% if report.organization %}
    <span class="inline-flex items-center rounded-md border border-blue-500/20 bg-blue-500/10 px-2 py-0.5 text-[10px] font-bold text-blue-500">{{ report.organization.name }}</span>
    {% else %}—{% endif %}
</div>
{% endif %}
```

4. Rebalancear los `col-span` para que sumen 12 en las cuatro combinaciones (labs on/off × cliente visible/oculto). Tabla de referencia:

| labs | cliente | Report | Machine | Lab | Client | Date | Condition | Mgmt |
|---|---|---|---|---|---|---|---|---|
| on | on | 2 | 2 | 2 | 2 | 1 | 1 | 2 |
| on | off | 2 | 2 | 2 | — | 2 | 2 | 2 |
| off | on | 2 | 2 | — | 2 | 2 | 2 | 2 |
| off | off | 3 | 3 | — | — | 2 | 2 | 2 |

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test apps.reports.tests.test_client_attribution apps.reports.tests.test_templates -v 2`
Expected: PASS.

---

### Task 4: Umbrales — columna, filtro y scoping

**Files:**
- Modify: `apps/reports/views.py` (`AnalysisThresholdListView`)
- Modify: `apps/reports/filtersets.py` (`AnalysisThresholdFilter`)
- Modify: `templates/reports/analysis_threshold/list.html`
- Test: `apps/reports/tests/test_client_attribution.py` (append)

**Interfaces:**
- Consumes: `ClientAttributionMixin` (Task 2), `scope_organization_filter(..., include_self=False)` (Task 1).
- Produces: `AnalysisThresholdFilter.organization` (declared `ModelChoiceFilter` with `field_name="component_type__organization"`).

- [ ] **Step 1: Write the failing tests**

Agregar en `apps/reports/tests/test_client_attribution.py`:

```python
class ThresholdClientAttributionTests(TestCase):
    """Client attribution and scoping for the threshold list."""

    def setUp(self) -> None:
        self.lab = organization_factories.OrganizationFactory(
            slug="ta-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="ta-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.other = organization_factories.OrganizationFactory(
            slug="ta-other", kind=choices.OrganizationKind.LAB
        )
        self.lab_threshold = factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.lab
            ),
            category="wear_metals",
            parameter="iron_fe",
        )
        self.final_threshold = factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.final
            ),
            category="wear_metals",
            parameter="iron_fe",
        )
        self.other_threshold = factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.other
            ),
            category="wear_metals",
            parameter="iron_fe",
        )
        self.global_threshold = factories.AnalysisThresholdFactory(
            component_type=None, category="wear_metals", parameter="iron_fe"
        )
        self.lab_user = user_for(self.lab)
        self.final_user = user_for(self.final)

    def _queryset_ids(self) -> set[int]:
        view = report_views.AnalysisThresholdListView()
        view.request = SimpleNamespace(user=self.lab_user)
        return set(view.get_queryset().values_list("id", flat=True))

    def test_list_scoped_to_subtree_and_globals(self) -> None:
        self.assertEqual(
            self._queryset_ids(),
            {self.lab_threshold.id, self.final_threshold.id, self.global_threshold.id},
        )

    def test_list_excludes_foreign_organizations(self) -> None:
        self.assertNotIn(self.other_threshold.id, self._queryset_ids())

    def test_select_related_joins_component_type_organization(self) -> None:
        view = report_views.AnalysisThresholdListView()
        view.request = SimpleNamespace(user=self.lab_user)
        related = view.get_queryset().query.select_related
        self.assertIn("component_type", related)
        self.assertIn("organization", related["component_type"])

    def test_show_organization_true_for_parent(self) -> None:
        self.assertTrue(list_context(report_views.AnalysisThresholdListView, self.lab_user)["show_organization"])

    def test_show_organization_false_for_leaf(self) -> None:
        self.assertFalse(list_context(report_views.AnalysisThresholdListView, self.final_user)["show_organization"])

    def test_organization_filter_lists_strict_children(self) -> None:
        filterset = filtersets.AnalysisThresholdFilter(
            queryset=models.AnalysisThreshold.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(filterset.filters["organization"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.final.id})

    def test_filter_by_organization(self) -> None:
        filterset = filtersets.AnalysisThresholdFilter(
            {"organization": self.final.pk},
            queryset=models.AnalysisThreshold.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(filterset.qs.values_list("id", flat=True))
        self.assertEqual(ids, {self.final_threshold.id})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.reports.tests.test_client_attribution.ThresholdClientAttributionTests -v 2`
Expected: FAIL (`show_organization` missing / filter missing / unscoped queryset).

- [ ] **Step 3: Implement the view**

En `apps/reports/views.py`:

```python
class AnalysisThresholdListView(
    core_mixins.ClientAttributionMixin, core_mixins.BaseListView
):
    """List view for AnalysisThreshold model."""

    model = models.AnalysisThreshold
    permission_required = "reports.view_analysisthreshold"
    filterset_class = filtersets.AnalysisThresholdFilter
    template_name = "reports/analysis_threshold/list.html"
    context_object_name = "thresholds"
    client_organization_path = "component_type__organization"

    def get_queryset(self) -> QuerySet:
        """Return subtree thresholds plus the global defaults."""
        queryset = super().get_queryset()
        visible = scoping.user_visible_organization_ids(
            scoping.request_user(getattr(self, "request", None))
        )
        if visible is None:
            return queryset
        return queryset.filter(
            Q(component_type__isnull=True)
            | Q(component_type__organization_id__in=visible)
        )
```

- [ ] **Step 4: Implement the filter**

En `AnalysisThresholdFilter`:

```python
organization = django_filters.ModelChoiceFilter(
    field_name="component_type__organization",
    queryset=organization_models.Organization.objects.all(),
    empty_label=_("All Clients"),
    label=_("Client"),
)
```

Agregar `"organization"` a `Meta.fields` y, en `__init__`:

```python
scoping.scope_organization_filter(self, include_self=False)
```

- [ ] **Step 5: Update the template**

En `templates/reports/analysis_threshold/list.html`:

1. Agregar el select "Cliente" condicionado por `show_organization` (usar `md:col-span-2`).
2. Ajustar el grid del formulario: con cliente visible, search 5 + client 2 + category 2 + is_active 2 + button 1 = 12.
3. Agregar la columna "Cliente" en encabezado y filas, condicionada por `show_organization`, con `threshold.component_type.organization.name` o "—".
4. Rebalancear: Parameter 3→2 y Management 3→2 cuando aparece la columna (2+2+2+2+1+1+2 = 12).

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test apps.reports.tests.test_client_attribution -v 2`
Expected: PASS.

---

### Task 5: Verificación final

- [ ] **Step 1: Run the affected suites**

Run: `python manage.py test apps.reports apps.organizations apps.core -v 2`
Expected: PASS.

- [ ] **Step 2: Lint and format check**

Run: `ruff check apps/organizations/scoping.py apps/core/mixins/views.py apps/reports/views.py apps/reports/filtersets.py apps/reports/tests/test_client_attribution.py`
Expected: no errors. Note: `ruff check apps docs` y `ruff format --check apps` reportan deuda preexistente del repo (p. ej. `apps/reports/views.py` ya estaba sin formatear en `HEAD`, en líneas no tocadas por este plan); no se corrige para no generar ruido ajeno.

- [ ] **Step 3: Smoke-test the templates**

Run: `python manage.py test apps.reports.tests.test_templates -v 2`
Expected: PASS.
