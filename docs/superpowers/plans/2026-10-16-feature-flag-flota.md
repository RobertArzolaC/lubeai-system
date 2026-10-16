# Feature flag de Flota (ENABLE_FLEET) — Plan de implementación

> **Para el agente implementador:** SUB-SKILL REQUERIDO: usa `superpowers:executing-plans` (ejecución nativa) o `superpowers:subagent-driven-development` (tarea por tarea con revisor). Los pasos usan casillas (`- [ ]`).

**Goal:** Ocultar la flota en toda la interfaz (formulario/listado/detalle de máquina, detalle de branch, menú lateral, filtros/gráfico/tabla del dashboard) mediante un feature flag gestionado con django-constance (`ENABLE_FLEET`, por defecto `False`), sin romper ni alterar las rutas de flota.

**Architecture:** El flag vive en `CONSTANCE_CONFIG`. El backend Python lo lee con `from constance import config`; las plantillas lo leen con `{{ config.ENABLE_FLEET }}` (el `constance.context_processors.config` ya está registrado en `config/settings/base.py`). El gating es exclusivamente de presentación: no se tocan modelos, migraciones, URLs ni permisos. Donde se oculta un campo/columna se rebalancean las rejillas (`grid`/`col-span`) para no dejar huecos. El JS del dashboard lee el estado del flag desde un `data-*` del contenedor.

**Tech Stack:** Django 6.0, django-constance 4.3.5, plantillas Django + Tailwind (TailAdmin), ApexCharts (JS vanilla en `static/js/dashboard.js`), tests con `unittest` (Django `TestCase`) y `factory_boy`.

**Spec:** decisiones acordadas con el usuario:
- Alcance: "todo el sistema" (equipment + dashboard + menú + breadcrumbs revisados).
- Mecanismo: django-constance (editable en admin, igual que `ENABLE_SEND_EMAIL`).
- Flag apagado: solo se oculta la UI; las rutas de flota siguen accesibles.
- Nombre/valor: `ENABLE_FLEET = False`.

## Global Constraints

- Código, comentarios y docstrings en **inglés** (AGENTS.md). Este plan y la comunicación van en español.
- Tipado y docstrings PEP 257 en cada función/clase que se modifique; mantener comentarios existentes.
- No modificar modelos, migraciones, URLs, permisos ni la app `alerts`/`reports` (no referencian flota).
- `ENABLE_FLEET` por defecto `False`.
- Con el flag apagado, `/fleets/...` sigue respondiendo (no bloqueo de rutas).
- Con `ENABLE_FLEET=True` el comportamiento visible no cambia respecto a hoy.
- Tests: `unittest` + factories del proyecto; comando `uv run python manage.py test <target>`.
- Lint: `uv run ruff check <paths>`.
- Ocultar campos requiere **omitir el markup y rebalancear la rejilla**, nunca dejarlo oculto con CSS (evita huecos).

## Review Focus

1. **Máquina con flota existente + flag apagado:** guardar el formulario de máquina **no debe** borrar `machine.fleet` (el campo se excluye, no se envía vacío).
2. **Dashboard con flag apagado:** no debe existir `#chart-fleet` ni el `<select name="fleet">`; la tabla debe tener 5 columnas y el filtrado por condición del gráfico debe seguir funcionando (el selector JS no puede depender de `data-fleet`).
3. **Sin `config` en el contexto** (tests que redefinen `context_processors` sin constance): las plantillas no deben lanzar error; `{% if config.ENABLE_FLEET %}` debe evaluarse a falsy.
4. **Usuario con solo `view_fleet` + flag apagado:** no debe aparecer un encabezado "Equipment" vacío en el menú.
5. **Flag encendido:** reaparecen menú, campo, filtro, columna, gráfico y tabla de 6 columnas (regresión visual revisada).

---

## File Structure

- **Modify** `config/settings/tools/django_constance.py` — añade `ENABLE_FLEET` al `CONSTANCE_CONFIG` y a `CONSTANCE_CONFIG_FIELDSETS`.
- **Modify** `apps/equipment/forms.py` — `MachineForm` oculta `fleet` cuando el flag está apagado.
- **Modify** `apps/equipment/views.py` — `MachineListView.get_queryset` deja de hacer `select_related("fleet")` cuando el flag está apagado.
- **Modify** `templates/equipment/machine/list.html` — columna y filtro de flota condicionales + rebalanceo de rejilla.
- **Modify** `templates/equipment/machine/detail.html` — bloque "Fleet" condicional + rebalanceo.
- **Modify** `templates/equipment/branch/detail.html` — etiqueta de flota por máquina condicional.
- **Modify** `templates/includes/aside.html` — ítem de menú "Fleets" y encabezado de grupo condicionales.
- **Modify** `templates/dashboard/includes/filters.html` — `<select name="fleet">` condicional.
- **Modify** `templates/dashboard/includes/charts.html` — tarjeta "Alerts by Fleet" condicional + rejilla rebalanceada.
- **Modify** `templates/dashboard/includes/tabs.html` — `<th>`/`<td>` de flota condicionales + `colspan` del estado vacío.
- **Modify** `templates/dashboard/index.html` — `data-fleet-enabled` en `#dashboard-root`.
- **Modify** `static/js/dashboard.js` — columnas de tabla y filtro de tabla dependientes del flag.
- **Modify** `apps/equipment/tests/test_forms.py`, `apps/equipment/tests/test_templates.py` — tests.
- **Create** `apps/equipment/tests/test_feature_flag.py` — test del flag.
- **Modify** `locale/es/LC_MESSAGES/django.po` (+ `.mo`) — traducción de la etiqueta nueva.
- **Sin cambios (revisado):** `apps/core/breadcrumbs.py` (las páginas de flota siguen accesibles, el crumb sigue siendo válido), `apps/equipment/filtersets.py` (`MachineFilter`/`FleetFilter` se mantienen), `apps/equipment/urls.py`, `apps/dashboard/filtersets.py`, `apps/dashboard/services/dashboard_service.py`, `apps/equipment/admin.py`, `templates/equipment/fleet/*`.

---

## Task 1: Flag `ENABLE_FLEET` en Constance

**Files:**
- Modify: `config/settings/tools/django_constance.py`
- Test: `apps/equipment/tests/test_feature_flag.py`

**Interfaces:**
- Produces: `config.ENABLE_FLEET: bool` (por defecto `False`), en el fieldset "1. General Options". En plantillas: `{{ config.ENABLE_FLEET }}`.

- [ ] **Step 1: Escribe el test que falla**

```python
# apps/equipment/tests/test_feature_flag.py
"""Tests for the fleet feature flag."""

from constance import config
from constance.test import override_config
from django.test import TestCase


class FleetFeatureFlagTests(TestCase):
    """``ENABLE_FLEET`` controls fleet visibility across the UI."""

    def test_defaults_to_false(self) -> None:
        """Fleet is hidden by default."""
        self.assertFalse(config.ENABLE_FLEET)

    @override_config(ENABLE_FLEET=True)
    def test_can_be_enabled(self) -> None:
        """The flag can be turned on."""
        self.assertTrue(config.ENABLE_FLEET)
```

- [ ] **Step 2: Ejecuta el test y verifica que falla**

Run: `uv run python manage.py test apps.equipment.tests.test_feature_flag`
Expected: FAIL — `AttributeError`/`False` inesperado en `test_can_be_enabled` (la clave no existe en `CONSTANCE_CONFIG`).

- [ ] **Step 3: Añade el flag en `config/settings/tools/django_constance.py`**

Añade la clave al final de `CONSTANCE_CONFIG`:

```python
    "ENABLE_FLEET": (False, _("Enable fleet management")),
```

Añade `"ENABLE_FLEET"` a la tupla `fields` del fieldset `"1. General Options"`.

- [ ] **Step 4: Ejecuta el test y verifica que pasa**

Run: `uv run python manage.py test apps.equipment.tests.test_feature_flag`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add config/settings/tools/django_constance.py apps/equipment/tests/test_feature_flag.py
git commit -m "feat(equipment): add ENABLE_FLEET feature flag"
```

---

## Task 2: Ocultar el campo Flota en `MachineForm`

**Files:**
- Modify: `apps/equipment/forms.py` (clase `MachineForm`, ~línea 85)
- Test: `apps/equipment/tests/test_forms.py`

**Interfaces:**
- Consumes: `config.ENABLE_FLEET` (Task 1).
- Produces: `MachineForm` sin la clave `"fleet"` en `self.fields` cuando el flag está apagado; sin cambios cuando está encendido.

- [ ] **Step 1: Escribe los tests que fallan** (añádelos a `MachineFormTests` en `apps/equipment/tests/test_forms.py`)

```python
    @override_config(ENABLE_FLEET=False)
    def test_fleet_field_hidden_when_flag_disabled(self) -> None:
        """The fleet field is removed from the form when the flag is off."""
        form = forms.MachineForm()
        self.assertNotIn("fleet", form.fields)

    @override_config(ENABLE_FLEET=True)
    def test_fleet_field_present_when_flag_enabled(self) -> None:
        """The fleet field is available when the flag is on."""
        form = forms.MachineForm()
        self.assertIn("fleet", form.fields)

    @override_config(ENABLE_FLEET=False)
    def test_saving_without_fleet_keeps_existing_value(self) -> None:
        """Saving a machine with the flag off must not clear its fleet."""
        fleet = FleetFactory()
        machine = MachineFactory(fleet=fleet)
        form = forms.MachineForm(
            data={
                "name": machine.name,
                "serial_number": machine.serial_number,
                "model": machine.model,
                "is_active": True,
            },
            instance=machine,
        )
        self.assertTrue(form.is_valid())
        form.save()
        machine.refresh_from_db()
        self.assertEqual(machine.fleet, fleet)
```

Añade los imports al inicio del archivo:

```python
from constance.test import override_config

from apps.equipment.factories import FleetFactory, MachineFactory
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.equipment.tests.test_forms.MachineFormTests`
Expected: FAIL en `test_fleet_field_hidden_when_flag_disabled` (el campo sigue presente).

- [ ] **Step 3: Implementa en `apps/equipment/forms.py`**

Añade el import:

```python
from constance import config
```

Añade un `__init__` a `MachineForm`:

```python
    def __init__(self, *args, **kwargs) -> None:
        """Hide the fleet field when the fleet feature flag is disabled.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, **kwargs)
        if not config.ENABLE_FLEET:
            self.fields.pop("fleet", None)
```

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.equipment.tests.test_forms`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/equipment/forms.py apps/equipment/tests/test_forms.py
git commit -m "feat(equipment): hide machine fleet field behind feature flag"
```

---

## Task 3: Listado de máquinas (columna + filtro + query)

**Files:**
- Modify: `templates/equipment/machine/list.html`
- Modify: `apps/equipment/views.py` (`MachineListView.get_queryset`, ~línea 16)
- Test: `apps/equipment/tests/test_templates.py`

**Interfaces:**
- Consumes: `{{ config.ENABLE_FLEET }}` (plantillas), `config.ENABLE_FLEET` (vista).
- Produces: rejilla siempre de 12 columnas; sin `id_fleet` ni cabecera "Fleet" cuando el flag está apagado.

- [ ] **Step 1: Escribe los tests que fallan** (añade a `EquipmentTemplateRenderingTests`)

```python
    @override_config(ENABLE_FLEET=False)
    def test_machine_list_hides_fleet_when_flag_disabled(self) -> None:
        """The machine list hides the fleet filter and column when off."""
        response = self.client.get(reverse("apps.equipment:machine_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="fleet"')

    @override_config(ENABLE_FLEET=True)
    def test_machine_list_shows_fleet_when_flag_enabled(self) -> None:
        """The machine list shows the fleet filter when on."""
        response = self.client.get(reverse("apps.equipment:machine_list"))
        self.assertContains(response, 'name="fleet"')
```

Añade `from constance.test import override_config` a los imports del archivo.

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates.EquipmentTemplateRenderingTests`
Expected: FAIL en `test_machine_list_hides_fleet_when_flag_disabled` (el `<select name="fleet">` sigue presente).

- [ ] **Step 3: Edita `templates/equipment/machine/list.html`**

En la tarjeta de filtros (`<form ... class="grid grid-cols-1 gap-4 md:grid-cols-12 ...">`):

1. Envuelve el `<div class="md:col-span-2">` de flota (el que contiene `filter.form.fleet`) con `{% if config.ENABLE_FLEET %}...{% endif %}`.
2. Rebalancea para sumar 12:
   - `<div class="md:col-span-3">` (branch) → `class="md:col-span-{% if config.ENABLE_FLEET %}3{% else %}4{% endif %}"`.
   - `<div class="md:col-span-2">` (is_active) → `class="md:col-span-{% if config.ENABLE_FLEET %}2{% else %}3{% endif %}"`.

En la cabecera de tabla (`<div class="grid grid-cols-12 ...">`):

3. Envuelve el `<div class="col-span-2 ...">` que contiene `{% trans "Fleet" %}` con `{% if config.ENABLE_FLEET %}`.
4. Rebalancea: branch `col-span-2` → `class="col-span-{% if config.ENABLE_FLEET %}2{% else %}3{% endif %}"`; status `col-span-2` → `class="col-span-{% if config.ENABLE_FLEET %}2{% else %}3{% endif %}"`.

En cada fila de máquina (`<div class="grid grid-cols-12 ...">`):

5. Envuelve el `<div class="col-span-2 ...">` que renderiza `machine.fleet` con `{% if config.ENABLE_FLEET %}`.
6. Aplica el mismo rebalanceo de `col-span` a las celdas branch y status de la fila.

- [ ] **Step 4: Edita `apps/equipment/views.py`**

En `MachineListView.get_queryset`, evita el join innecesario cuando el flag está apagado:

```python
    def get_queryset(self) -> QuerySet:
        """Return machines with related objects to avoid N+1 queries."""
        related = ["branch"]
        if config.ENABLE_FLEET:
            related.append("fleet")
        return models.Machine.objects.select_related(*related)
```

Añade `from constance import config` a los imports.

- [ ] **Step 5: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/equipment/machine/list.html apps/equipment/views.py apps/equipment/tests/test_templates.py
git commit -m "feat(equipment): gate fleet column and filter in machine list"
```

---

## Task 4: Detalle de máquina y de branch

**Files:**
- Modify: `templates/equipment/machine/detail.html` (bloque "Location", ~líneas 60-80)
- Modify: `templates/equipment/branch/detail.html` (~líneas 87-96)
- Test: `apps/equipment/tests/test_templates.py`

**Interfaces:**
- Consumes: `{{ config.ENABLE_FLEET }}`.
- Produces: `Location` en una sola columna cuando el flag está apagado.

- [ ] **Step 1: Escribe los tests que fallan**

```python
    @override_config(ENABLE_FLEET=False)
    def test_machine_detail_hides_fleet_when_flag_disabled(self) -> None:
        """The machine detail hides the fleet link when off."""
        fleet = FleetFactory()
        machine = MachineFactory(fleet=fleet)
        response = self.client.get(
            reverse("apps.equipment:machine_detail", kwargs={"pk": machine.pk})
        )
        self.assertNotContains(
            response, reverse("apps.equipment:fleet_detail", kwargs={"pk": fleet.pk})
        )

    @override_config(ENABLE_FLEET=True)
    def test_machine_detail_shows_fleet_when_flag_enabled(self) -> None:
        """The machine detail shows the fleet link when on."""
        fleet = FleetFactory()
        machine = MachineFactory(fleet=fleet)
        response = self.client.get(
            reverse("apps.equipment:machine_detail", kwargs={"pk": machine.pk})
        )
        self.assertContains(
            response, reverse("apps.equipment:fleet_detail", kwargs={"pk": fleet.pk})
        )
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates`
Expected: FAIL en `test_machine_detail_hides_fleet_when_flag_disabled`.

- [ ] **Step 3: Edita `templates/equipment/machine/detail.html`**

1. La `<dl>` de "Location": cambia la clase a
   `class="grid grid-cols-1 gap-4 {% if config.ENABLE_FLEET %}sm:grid-cols-2{% endif %}"`.
2. Envuelve el `<div>` que contiene el `<dt>{% trans "Fleet" %}</dt>` y el enlace a `fleet_detail` con `{% if config.ENABLE_FLEET %}...{% endif %}`.

- [ ] **Step 4: Edita `templates/equipment/branch/detail.html`**

Envuelve el `<span>` de la flota por máquina con el flag:

```django
{% if config.ENABLE_FLEET and machine.fleet %}
<span class="text-xs font-semibold text-bodydark2">{{ machine.fleet.name }}</span>
{% endif %}
```

- [ ] **Step 5: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/equipment/machine/detail.html templates/equipment/branch/detail.html apps/equipment/tests/test_templates.py
git commit -m "feat(equipment): gate fleet display in machine and branch detail"
```

---

## Task 5: Menú lateral (dashboard aside)

**Files:**
- Modify: `templates/includes/aside.html` (~líneas 34-66)
- Test: `apps/equipment/tests/test_templates.py` (clases `DashboardModuleAccessTests` y una nueva)

**Interfaces:**
- Consumes: `{{ config.ENABLE_FLEET }}` y `perms.equipment.view_fleet`.
- Produces: sin ítem "Fleets" ni encabezado "Equipment" huérfano cuando el flag está apagado.

- [ ] **Step 1: Escribe/actualiza los tests**

Actualiza `DashboardModuleAccessTests.test_dashboard_shows_equipment_links_for_authorized_user` para activar el flag mediante `@override_config(ENABLE_FLEET=True)` (sigue afirmando que está `fleet_list`). Añade:

```python
    @override_config(ENABLE_FLEET=False)
    def test_dashboard_hides_fleet_link_when_flag_disabled(self) -> None:
        """A superuser does not see the fleet link while the flag is off."""
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertNotContains(response, reverse("apps.equipment:fleet_list"))

    @override_config(ENABLE_FLEET=False)
    def test_equipment_header_hidden_for_view_only_fleet_user(self) -> None:
        """A view_fleet-only user sees no orphan equipment header when off."""
        user = UserFactory()
        grant_permissions(user, "view_fleet")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertNotContains(response, "Equipment")
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates`
Expected: FAIL en los tests nuevos (con `ENABLE_FLEET=False` el ítem de flota aún se renderiza).

- [ ] **Step 3: Edita `templates/includes/aside.html`**

1. Encabezado de grupo (línea ~34): añade la condición de flota solo cuando el flag esté activo:
   ```django
   {% if perms.equipment.view_machine or perms.equipment.view_branch or perms.equipment.view_componenttype or config.ENABLE_FLEET and perms.equipment.view_fleet %}
   ```
2. Ítem de menú de flota (línea ~58): cambia a
   ```django
   {% if config.ENABLE_FLEET and perms.equipment.view_fleet %}
   ```

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/includes/aside.html apps/equipment/tests/test_templates.py
git commit -m "feat(dashboard): hide fleet menu item behind feature flag"
```

---

## Task 6: Dashboard (filtro, gráfico, tabla y JS)

**Files:**
- Modify: `templates/dashboard/includes/filters.html`
- Modify: `templates/dashboard/includes/charts.html`
- Modify: `templates/dashboard/includes/tabs.html`
- Modify: `templates/dashboard/index.html`
- Modify: `static/js/dashboard.js`
- Test: `apps/equipment/tests/test_templates.py` (render real del dashboard)

**Interfaces:**
- Consumes: `{{ config.ENABLE_FLEET }}`; atributo `data-fleet-enabled="true|false"` en `#dashboard-root`.
- Produces: `#dashboard-root[data-fleet-enabled]` y tabla del dashboard con 5/6 columnas según el flag.

- [ ] **Step 1: Escribe los tests que fallan**

```python
    @override_config(ENABLE_FLEET=False)
    def test_dashboard_hides_fleet_widgets_when_flag_disabled(self) -> None:
        """Fleet filter and chart are absent and the JS flag is false."""
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(response, 'data-fleet-enabled="false"')
        self.assertNotContains(response, "chart-fleet")
        self.assertNotContains(response, "Alerts by Fleet")

    @override_config(ENABLE_FLEET=True)
    def test_dashboard_shows_fleet_widgets_when_flag_enabled(self) -> None:
        """Fleet filter and chart are present and the JS flag is true."""
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(response, 'data-fleet-enabled="true"')
        self.assertContains(response, "chart-fleet")
        self.assertContains(response, "Alerts by Fleet")
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates`
Expected: FAIL (no existe `data-fleet-enabled`).

- [ ] **Step 3: Edita `templates/dashboard/index.html`**

Añade el atributo al contenedor:

```django
<div
    id="dashboard-root"
    data-data-url="{% url 'apps.dashboard:data' %}"
    data-fleet-enabled="{% if config.ENABLE_FLEET %}true{% else %}false{% endif %}"
    class="flex flex-col gap-6"
>
```

- [ ] **Step 4: Edita `templates/dashboard/includes/filters.html`**

Envuelve el `<label>` del `<select name="fleet">` con `{% if config.ENABLE_FLEET %}...{% endif %}`.

- [ ] **Step 5: Edita `templates/dashboard/includes/charts.html`**

1. Rejilla raíz: `class="grid grid-cols-1 gap-4 {% if config.ENABLE_FLEET %}xl:grid-cols-3{% else %}xl:grid-cols-2{% endif %}"`.
2. Tarjeta "Samples per Month": añade `{% if config.ENABLE_FLEET %}xl:col-span-2{% endif %}` a su clase (mantiene el layout actual cuando el flag está encendido y produce una rejilla 2×2 limpia cuando está apagado).
3. Envuelve la tarjeta "Alerts by Fleet" completa (`<div id="chart-fleet">` incluido) con `{% if config.ENABLE_FLEET %}...{% endif %}`.

- [ ] **Step 6: Edita `templates/dashboard/includes/tabs.html`**

1. Envuelve `<th class="px-3 py-2">{% trans "Fleet" %}</th>` con `{% if config.ENABLE_FLEET %}`.
2. Envuelve el `<td class="px-3 py-2">{{ row.fleet }}</td>` con `{% if config.ENABLE_FLEET %}`.
3. Estado vacío: `colspan="{% if config.ENABLE_FLEET %}6{% else %}5{% endif %}"`.

- [ ] **Step 7: Edita `static/js/dashboard.js`**

1. Tras leer `currentData`, añade:

```js
    var fleetEnabled = root.getAttribute("data-fleet-enabled") === "true";
```

2. En `renderTable`, construye las celdas condicionalmente y ajusta el `colspan`:

```js
            if (fleetEnabled) {
                row.setAttribute("data-fleet", report.fleet || "");
            }
            var values = [
                report.lab_number,
                report.machine
            ];
            if (fleetEnabled) values.push(report.fleet);
            values.push(report.component, report.sample_date, report.condition_display);
            values.forEach(function (value) {
                var cell = document.createElement("td");
                cell.className = "px-3 py-2";
                cell.textContent = value == null ? "" : value;
                row.appendChild(cell);
            });
```

   y `emptyCell.colSpan = fleetEnabled ? 6 : 5;`.

3. En `filterTable`, cambia el selector y el criterio de flota:

```js
            body.querySelectorAll("tr[data-condition]"),
            function (row) {
                var conditionOk = !criteria.condition
                    || row.getAttribute("data-condition") === criteria.condition;
                var fleetOk = !fleetEnabled || !criteria.fleet
                    || row.getAttribute("data-fleet") === criteria.fleet;
                var visible = conditionOk && fleetOk;
```

   `renderFleetChart` ya retorna temprano si `#chart-fleet` no existe; déjalo igual.

- [ ] **Step 8: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.equipment.tests.test_templates`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add templates/dashboard/index.html templates/dashboard/includes/filters.html templates/dashboard/includes/charts.html templates/dashboard/includes/tabs.html static/js/dashboard.js apps/equipment/tests/test_templates.py
git commit -m "feat(dashboard): gate fleet filter, chart and table column behind feature flag"
```

---

## Task 7: i18n, limpieza y revisión (django-reviewer)

**Files:**
- Modify: `locale/es/LC_MESSAGES/django.po` (+ `.mo`)

**Interfaces:**
- Consumes: la etiqueta `_("Enable fleet management")` (Task 1).
- Produces: traducción al español compilada.

- [ ] **Step 1: Actualiza los catálogos**

Run:
```bash
uv run python manage.py makemessages -l es -l en
```
Añade la traducción en `locale/es/LC_MESSAGES/django.po`:

```po
msgid "Enable fleet management"
msgstr "Habilitar gestión de flotas"
```

Compila:
```bash
uv run python manage.py compilemessages
```
Expected: se regenera `locale/es/LC_MESSAGES/django.mo`.

- [ ] **Step 2: Limpieza de código sin uso**

Revisa el diff completo (`git diff`) y elimina:
- Cualquier atributo `data-fleet` que se hubiera quedado huérfano en plantillas.
- Ramas muertas en `static/js/dashboard.js` (p. ej. usos de `data-fleet` fuera de `fleetEnabled`).
- Imports sin uso en `apps/equipment/forms.py`/`apps/equipment/views.py`.
No elimines `get_alerts_by_fleet`, `recent_reports[*]["fleet"]`, `MachineFilter.fleet` ni las vistas/URLs de flota: siguen usándose cuando el flag está encendido.

- [ ] **Step 3: Ejecuta toda la suite de las apps tocadas**

Run:
```bash
uv run python manage.py test apps.equipment apps.dashboard apps.alerts
```
Expected: PASS (0 fallos). Presta atención a `DashboardModuleAccessTests` (Task 5) y a `apps.alerts.tests` (no debe verse afectada).

- [ ] **Step 4: Lint**

Run: `uv run ruff check apps/equipment config/settings/tools/django_constance.py`
Expected: `All checks passed!`.

- [ ] **Step 5: Revisión con `django-reviewer`**

Invoca el skill `django-reviewer` sobre el diff generado (archivos de `apps/equipment/*` y `config/settings/tools/django_constance.py`). Reporta hallazgos; aplica solo refinamientos elegibles que no cambien comportamiento. Verifica de nuevo (Step 3-4) tras cualquier edición.

- [ ] **Step 6: Commit**

```bash
git add locale/ static/js/dashboard.js apps/equipment config/settings/tools/django_constance.py
git commit -m "chore: translate fleet flag and clean up unused fleet code"
```

---

## Criterios de aceptación

- [ ] `ENABLE_FLEET` es editable en el admin de Constance y por defecto es `False`.
- [ ] Flag apagado: sin campo/columna/filtro de flota en máquina, sin flota en detalle de máquina/branch, sin ítem de menú, sin filtro/gráfico/columna de flota en el dashboard; las rejillas quedan balanceadas (12 columnas / 2×2).
- [ ] Flag encendido: toda la UI de flota vuelve exactamente como hoy.
- [ ] Guardar una máquina con flota existente y el flag apagado conserva su flota.
- [ ] `/fleets/...` sigue respondiendo con el flag apagado.
- [ ] Suite de `equipment`, `dashboard` y `alerts` en verde; `ruff` limpio; revisión `django-reviewer` aplicada.
