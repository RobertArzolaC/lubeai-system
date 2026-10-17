# Feature flag de Laboratorios (ENABLE_LABS) — Plan de implementación

> **Para el agente implementador:** SUB-SKILL REQUERIDO: usa `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` (ejecución nativa). Los pasos usan casillas (`- [ ]`).

**Goal:** Ocultar todo lo relacionado con "laboratorio" en la interfaz (menú lateral, listado, y las referencias dentro de Informes: columna/filtro/campo/filtro de export) mediante un feature flag gestionado con django-constance (`ENABLE_LABS`, por defecto `False`), desactivando los enlaces a rutas de laboratorio, sin bloquear dichas rutas.

**Architecture:** El flag vive en `CONSTANCE_CONFIG`. El backend lo lee con `from constance import config`; las plantillas con `{{ config.ENABLE_LABS }}` (el `constance.context_processors.config` ya está registrado en `config/settings/base.py`). El gating es exclusivamente de presentación: no se tocan modelos, migraciones, URLs ni permisos. Los formularios/filtros eliminan el campo `laboratory` cuando el flag está apagado (no se envía vacío). Se replica el patrón ya existente de `ENABLE_FLEET` (`docs/superpowers/plans/2026-10-16-feature-flag-flota.md`).

**Tech Stack:** Django 6.0, django-constance 4.3.5, django-filter 26.1, plantillas Django + Tailwind (TailAdmin), tests con `unittest` (Django `TestCase`) y `factory_boy`.

**Spec:** decisiones acordadas con el usuario:
- Alcance: **toda** la UI relacionada con laboratorio (menú + listado + referencias dentro de Informes).
- Mecanismo: django-constance (editable en admin, igual que `ENABLE_FLEET`).
- Flag apagado: solo se oculta en UI; **las rutas de laboratorio siguen respondiendo** (no se bloquean).
- Nombre/valor: `ENABLE_LABS = False`.
- Extra acordado: se corrige un *gap* preexistente del encabezado del grupo "Reports" añadiendo `perms.reports.view_component_analysis` a su condición.
- Comunicación y plan en español; código, comentarios y docstrings en inglés.

## Global Constraints

- Código, comentarios y docstrings en **inglés** (AGENTS.md). Este plan y la comunicación van en español.
- Tipado y docstrings PEP 257 en cada función/clase que se modifique; mantener comentarios existentes.
- No modificar modelos, migraciones, URLs, permisos ni la app `alerts`.
- `ENABLE_LABS` por defecto `False`.
- Con el flag apagado, `/laboratories/...` sigue respondiendo (no bloqueo de rutas).
- Con `ENABLE_LABS=True` el comportamiento visible no cambia respecto a hoy.
- Ocultar un campo/columna requiere **omitir el markup y rebalancear la rejilla** (12 columnas), nunca dejarlo oculto con CSS (evita huecos).
- Tests: `unittest` + factories del proyecto; comando `uv run python manage.py test <target>`.
- Lint: `uv run ruff check <paths>`.

## Review Focus

1. **Informe con laboratorio existente + flag apagado:** guardar el formulario de informe **no debe** borrar `report.laboratory` (el campo se excluye, no se envía vacío).
2. **Flag apagado en listado/export:** no debe existir `name="laboratory"`; el `{% with lab=filter.form.laboratory.value %}` no debe lanzar error al faltar el campo (se resuelve a vacío).
3. **Sin `config` en el contexto** (tests que redefinen `context_processors` sin constance): las plantillas no deben lanzar error; `{% if config.ENABLE_LABS %}` debe evaluarse a falsy.
4. **Usuario con solo `view_laboratory` + flag apagado:** no debe aparecer un encabezado "Informes" huérfano en el menú.
5. **Flag encendido:** reaparecen menú, columna, filtro, campo, enlace y filtro de export exactamente como hoy, con rejillas balanceadas (12 columnas).

---

## File Structure

- **Modify** `config/settings/tools/django_constance.py` — añade `ENABLE_LABS` al `CONSTANCE_CONFIG` y a `CONSTANCE_CONFIG_FIELDSETS`.
- **Modify** `apps/reports/forms.py` — `ReportForm` elimina `laboratory` cuando el flag está apagado.
- **Modify** `apps/reports/filtersets.py` — `ReportFilter` y `ReportExportFilter` eliminan el filtro `laboratory` cuando el flag está apagado.
- **Modify** `templates/includes/aside.html` — ítem de menú "Laboratories" y encabezado del grupo "Reports" condicionales (+ fix del encabezado para `view_component_analysis`).
- **Modify** `templates/reports/report/list.html` — columna y filtro de laboratorio condicionales + rebalanceo de rejilla.
- **Modify** `templates/reports/report/detail.html` — enlace de laboratorio desactivado (texto plano) cuando el flag está apagado.
- **Modify** `templates/reports/report/export.html` — filtro de laboratorio condicional.
- **Create** `apps/reports/tests/test_feature_flag.py`.
- **Modify** `apps/reports/tests/test_forms.py`, `apps/reports/tests/test_filtersets.py`, `apps/reports/tests/test_templates.py`.
- **Modify** `locale/es/LC_MESSAGES/django.po` (+ `.mo`) y `locale/en/LC_MESSAGES/django.po`.
- **Sin cambios (revisado, se mantiene por diseño):** `apps/reports/views.py` (`select_related("laboratory")` se conserva para el detalle y el export, evitando N+1; las vistas de laboratorio siguen accesibles), `apps/reports/urls.py`, `apps/reports/models.py`, `apps/reports/admin.py`, `apps/reports/services/report_export.py` (la columna "Laboratorio" del Excel es dato, no sección), `templates/reports/laboratory/*` (rutas activas).

---

## Task 1: Flag `ENABLE_LABS` en Constance

**Files:**
- Modify: `config/settings/tools/django_constance.py`
- Test: `apps/reports/tests/test_feature_flag.py` (crear)

**Interfaces:**
- Produces: `config.ENABLE_LABS: bool` (por defecto `False`), en el fieldset "1. General Options". En plantillas: `{{ config.ENABLE_LABS }}`.

- [ ] **Step 1: Escribe el test que falla**

```python
# apps/reports/tests/test_feature_flag.py
"""Tests for the laboratory feature flag."""

from constance import config
from constance.test import override_config
from django.test import TestCase


class LaboratoryFeatureFlagTests(TestCase):
    """``ENABLE_LABS`` controls laboratory visibility across the UI."""

    def test_defaults_to_false(self) -> None:
        """Laboratories are hidden by default."""
        self.assertFalse(config.ENABLE_LABS)

    @override_config(ENABLE_LABS=True)
    def test_can_be_enabled(self) -> None:
        """The flag can be turned on."""
        self.assertTrue(config.ENABLE_LABS)
```

- [ ] **Step 2: Ejecuta el test y verifica que falla**

Run: `uv run python manage.py test apps.reports.tests.test_feature_flag`
Expected: FAIL — `AttributeError`/`False` inesperado en `test_can_be_enabled` (la clave no existe en `CONSTANCE_CONFIG`).

- [ ] **Step 3: Añade el flag en `config/settings/tools/django_constance.py`**

Añade la clave al final de `CONSTANCE_CONFIG`:

```python
    "ENABLE_LABS": (False, _("Enable laboratory management")),
```

Añade `"ENABLE_LABS"` a la tupla `fields` del fieldset `"1. General Options"`.

- [ ] **Step 4: Ejecuta el test y verifica que pasa**

Run: `uv run python manage.py test apps.reports.tests.test_feature_flag`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add config/settings/tools/django_constance.py apps/reports/tests/test_feature_flag.py
git commit -m "feat(reports): add ENABLE_LABS feature flag"
```

---

## Task 2: `ReportForm` oculta el campo laboratorio

**Files:**
- Modify: `apps/reports/forms.py` (`ReportForm.__init__`, ~línea 105)
- Test: `apps/reports/tests/test_forms.py` (clase `ReportFormTests`)

**Interfaces:**
- Consumes: `config.ENABLE_LABS` (Task 1).
- Produces: `ReportForm` sin la clave `"laboratory"` en `self.fields` cuando el flag está apagado; sin cambios cuando está encendido.

- [ ] **Step 1: Escribe los tests que fallan** (añádelos a `ReportFormTests` en `apps/reports/tests/test_forms.py`)

```python
    @override_config(ENABLE_LABS=False)
    def test_laboratory_field_hidden_when_flag_disabled(self) -> None:
        """The laboratory field is removed from the form when the flag is off."""
        form = forms.ReportForm()
        self.assertNotIn("laboratory", form.fields)

    @override_config(ENABLE_LABS=True)
    def test_laboratory_field_present_when_flag_enabled(self) -> None:
        """The laboratory field is available when the flag is on."""
        form = forms.ReportForm()
        self.assertIn("laboratory", form.fields)

    @override_config(ENABLE_LABS=False)
    def test_saving_without_laboratory_keeps_existing_value(self) -> None:
        """Saving a report with the flag off must not clear its laboratory."""
        report = factories.ReportFactory(laboratory=self.laboratory)
        payload = self.report_payload()
        payload.pop("laboratory")
        payload.update(
            lab_number=report.lab_number,
            machine=report.machine_id,
            component=report.component_id,
        )
        form = forms.ReportForm(data=payload, instance=report)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        report.refresh_from_db()
        self.assertEqual(report.laboratory, self.laboratory)
```

Añade el import al inicio del archivo:

```python
from constance.test import override_config
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.reports.tests.test_forms.ReportFormTests`
Expected: FAIL en `test_laboratory_field_hidden_when_flag_disabled` (el campo sigue presente).

- [ ] **Step 3: Implementa en `apps/reports/forms.py`**

Añade el import:

```python
from constance import config
```

Reemplaza el cuerpo de `ReportForm.__init__` para conservar el comportamiento actual cuando el flag está encendido y eliminar el campo cuando está apagado:

```python
    def __init__(self, *args, **kwargs) -> None:
        """Limit relation choices to active records and mark required fields."""
        super().__init__(*args, **kwargs)
        self.fields["machine"].required = True
        self.fields["component"].required = True
        self.fields["lab_number"].required = True
        self.fields["sample_date"].required = True

        if config.ENABLE_LABS:
            self.fields["laboratory"].queryset = models.Laboratory.objects.filter(
                is_active=True
            )
        else:
            self.fields.pop("laboratory", None)

        self.fields["machine"].queryset = equipment_models.Machine.objects.filter(
            is_active=True
        )
        self.fields["component"].queryset = equipment_models.Component.objects.filter(
            is_active=True
        ).select_related("type")
```

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.reports.tests.test_forms`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/reports/forms.py apps/reports/tests/test_forms.py
git commit -m "feat(reports): hide laboratory field in report form behind feature flag"
```

---

## Task 3: Filtros de informe ocultan laboratorio

**Files:**
- Modify: `apps/reports/filtersets.py` (`ReportFilter` ~línea 39, `ReportExportFilter` ~línea 106)
- Test: `apps/reports/tests/test_filtersets.py`

**Interfaces:**
- Consumes: `config.ENABLE_LABS`.
- Produces: `ReportFilter.filters` y `ReportExportFilter.filters` sin la clave `"laboratory"` (y por tanto sin campo en `filter.form`) cuando el flag está apagado. En django-filter 26.1 el formulario se construye de forma perezosa desde `self.filters` (`FilterSet.form` es una `@property` que compila la primera vez que se accede), por lo que eliminarlo en `__init__` tras `super().__init__()` es suficiente.

- [ ] **Step 1: Escribe los tests que fallan** (añádelos a `ReportFilterTests` y `ReportExportFilterTests`)

```python
    @override_config(ENABLE_LABS=False)
    def test_laboratory_filter_hidden_when_flag_disabled(self) -> None:
        """The laboratory filter is removed from the report filter when off."""
        filterset = filtersets.ReportFilter(queryset=models.Report.objects.all())
        self.assertNotIn("laboratory", filterset.filters)
        self.assertNotIn("laboratory", filterset.form.fields)

    @override_config(ENABLE_LABS=True)
    def test_laboratory_filter_present_when_flag_enabled(self) -> None:
        """The laboratory filter is available when the flag is on."""
        filterset = filtersets.ReportFilter(queryset=models.Report.objects.all())
        self.assertIn("laboratory", filterset.filters)
```

```python
    @override_config(ENABLE_LABS=False)
    def test_export_laboratory_filter_hidden_when_flag_disabled(self) -> None:
        """The export laboratory filter is removed when off."""
        filterset = filtersets.ReportExportFilter(queryset=models.Report.objects.all())
        self.assertNotIn("laboratory", filterset.filters)
```

Añade `from constance.test import override_config` a los imports del archivo.

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.reports.tests.test_filtersets`
Expected: FAIL en los tests nuevos (el filtro sigue presente).

- [ ] **Step 3: Implementa en `apps/reports/filtersets.py`**

Añade el import:

```python
from constance import config
```

Añade un `__init__` a `ReportFilter` (tras su `class Meta`):

```python
    def __init__(self, *args, **kwargs) -> None:
        """Hide the laboratory filter when the flag is disabled."""
        super().__init__(*args, **kwargs)
        if not config.ENABLE_LABS:
            self.filters.pop("laboratory", None)
```

Añade el mismo `__init__` a `ReportExportFilter`. No modifiques `Meta.fields` ni las declaraciones de filtro (siguen usándose cuando el flag está encendido).

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.reports.tests.test_filtersets`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/reports/filtersets.py apps/reports/tests/test_filtersets.py
git commit -m "feat(reports): hide laboratory filters behind feature flag"
```

---

## Task 4: Menú lateral (dashboard aside) + fix del encabezado

**Files:**
- Modify: `templates/includes/aside.html` (~líneas 78-92)
- Test: `apps/reports/tests/test_templates.py`

**Interfaces:**
- Consumes: `{{ config.ENABLE_LABS }}`, `perms.reports.view_laboratory` y `perms.reports.view_component_analysis`.
- Produces: sin ítem "Laboratories" ni encabezado "Informes" huérfano cuando el flag está apagado; el encabezado también se muestra para usuarios con solo `view_component_analysis` (fix del *gap* preexistente).

- [ ] **Step 1: Escribe los tests que fallan** (clases nuevas en `apps/reports/tests/test_templates.py`)

```python
from constance.test import override_config
from django.contrib.auth.models import Permission
from django.template import Context, Template
from django.test import SimpleTestCase


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given reports permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="reports", codename__in=codenames
    )
    user.user_permissions.add(*permissions)


class ReportsMenuFlagTests(TestCase):
    """The laboratories menu entry is gated by the feature flag."""

    @override_config(ENABLE_LABS=False)
    def test_menu_hides_laboratory_link_when_flag_disabled(self) -> None:
        """A superuser does not see the laboratory link while the flag is off."""
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertNotContains(response, reverse("apps.reports:laboratory_list"))

    @override_config(ENABLE_LABS=True)
    def test_menu_shows_laboratory_link_when_flag_enabled(self) -> None:
        """A superuser sees the laboratory link when the flag is on."""
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(response, reverse("apps.reports:laboratory_list"))

    @override_config(ENABLE_LABS=False)
    def test_reports_header_hidden_for_view_only_laboratory_user(self) -> None:
        """A view_laboratory-only user sees no orphan reports header when off."""
        user = UserFactory()
        grant_permissions(user, "view_laboratory")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertNotContains(response, "Informes")

    def test_reports_header_visible_for_component_analysis_user(self) -> None:
        """A view_component_analysis-only user still sees the reports header."""
        user = UserFactory()
        grant_permissions(user, "view_component_analysis")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(response, "Informes")


class LaboratoryFlagMissingConfigTests(SimpleTestCase):
    """The laboratory gate degrades to falsy when ``config`` is not in context."""

    def test_flag_is_falsy_without_config_in_context(self) -> None:
        """A missing ``config`` object renders the branch as hidden, not an error."""
        template = Template("{% if config.ENABLE_LABS %}on{% else %}off{% endif %}")
        self.assertEqual(template.render(Context({})), "off")
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: FAIL en los tests nuevos (con `ENABLE_LABS=False` el ítem de laboratorio aún se renderiza; y con solo `view_component_analysis` no aparece "Informes").

- [ ] **Step 3: Edita `templates/includes/aside.html`**

Encabezado del grupo "Reports" (línea ~78): el término de laboratorio solo cuenta cuando el flag está activo, y se incluye el permiso de análisis de componentes (fix):

```django
{% if perms.reports.view_report or perms.reports.view_analysisthreshold or perms.reports.view_component_analysis or config.ENABLE_LABS and perms.reports.view_laboratory %}
```

Ítem de menú de laboratorios (línea ~84):

```django
{% if config.ENABLE_LABS and perms.reports.view_laboratory %}
```

Deja el resto del ítem (enlace `laboratory_list`, icono `flask-conical`, texto "Laboratories") sin cambios dentro del `if`.

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/includes/aside.html apps/reports/tests/test_templates.py
git commit -m "feat(reports): hide laboratories menu item behind feature flag"
```

---

## Task 5: Listado de informes (columna + filtro + rejilla)

**Files:**
- Modify: `templates/reports/report/list.html` (~líneas 70-101 y 115-165)
- Test: `apps/reports/tests/test_templates.py`

**Interfaces:**
- Consumes: `{{ config.ENABLE_LABS }}`.
- Produces: rejilla siempre de 12 columnas; sin `name="laboratory"` ni columna "Laboratorio" cuando el flag está apagado. El `{% with lab=filter.form.laboratory.value %}` se conserva (se resuelve a vacío, ya que el filtro no existe cuando está apagado).

- [ ] **Step 1: Escribe los tests que fallan** (clase nueva en `apps/reports/tests/test_templates.py`)

```python
class ReportListFlagTests(TestCase):
    """The report list laboratory column and filter are gated by the flag."""

    @override_config(ENABLE_LABS=False)
    def test_report_list_hides_laboratory_when_flag_disabled(self) -> None:
        """The report list hides the laboratory filter and column when off."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="laboratory"')
        self.assertNotContains(response, "Laboratorio")

    @override_config(ENABLE_LABS=True)
    def test_report_list_shows_laboratory_when_flag_enabled(self) -> None:
        """The report list shows the laboratory filter and column when on."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertContains(response, 'name="laboratory"')
```

Disponible por `ReportsTemplateRenderingTests` (superusuario con permiso); alternativamente hereda de esa clase. Ajusta como prefieras manteniendo el `force_login` de un usuario con `view_report`.

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: FAIL en los tests nuevos.

- [ ] **Step 3: Edita `templates/reports/report/list.html`**

**Filtros avanzados** (grid `md:grid-cols-12` con Laboratory / Machine / Component / is_active):

1. Envuelve el `<div class="md:col-span-3">` que contiene `filter.form.laboratory` (líneas ~83-86) con `{% if config.ENABLE_LABS %}...{% endif %}`.
2. Rebalancea los otros tres `<div class="md:col-span-3">` a
   `class="md:col-span-{% if config.ENABLE_LABS %}3{% else %}4{% endif %} ..."` (Machine, Component, is_active).
   (Apagado: 4+4+4 = 12. Encendido: 3+3+3+3 = 12.)

**Cabecera de tabla** (grid `grid-cols-12`):

3. Envuelve el `<div class="col-span-2">` con `{% trans "Laboratory" %}` (líneas ~122-124) con `{% if config.ENABLE_LABS %}`.
4. Rebalancea "Report" y "Machine / Component" a
   `class="col-span-{% if config.ENABLE_LABS %}2{% else %}3{% endif %} ..."`.
   (Apagado: 3+3+2+2+2 = 12. Encendido: 2×6 = 12.)

**Filas de informe** (grid `grid-cols-12`):

5. Envuelve el `<div class="col-span-2">` que renderiza `report.laboratory` (líneas ~151-153) con `{% if config.ENABLE_LABS %}`.
6. Aplica el mismo rebalanceo `col-span-{% if config.ENABLE_LABS %}2{% else %}3{% endif %}` a las celdas "Report" y "Machine / Component" de la fila.

No toques la línea `{% with lab=filter.form.laboratory.value ... %}`.

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/reports/report/list.html apps/reports/tests/test_templates.py
git commit -m "feat(reports): gate laboratory column and filter in report list"
```

---

## Task 6: Detalle del informe (desactivar enlace)

**Files:**
- Modify: `templates/reports/report/detail.html` (~líneas 52-59)
- Test: `apps/reports/tests/test_templates.py`

**Interfaces:**
- Consumes: `{{ config.ENABLE_LABS }}`.
- Produces: cuando el flag está apagado, el nombre del laboratorio se muestra como texto plano (sin enlace a `laboratory_detail`); cuando está encendido, el enlace reaparece.

- [ ] **Step 1: Escribe los tests que fallan**

```python
class ReportDetailFlagTests(TestCase):
    """The report detail laboratory link is gated by the flag."""

    @override_config(ENABLE_LABS=False)
    def test_report_detail_disables_laboratory_link_when_flag_disabled(self) -> None:
        """The report detail shows the laboratory as plain text (no link) when off."""
        laboratory = factories.LaboratoryFactory()
        report = factories.ReportFactory(laboratory=laboratory)
        response = self.client.get(
            reverse("apps.reports:report_detail", kwargs={"pk": report.pk})
        )
        self.assertContains(response, laboratory.name)
        self.assertNotContains(
            response,
            reverse("apps.reports:laboratory_detail", kwargs={"pk": laboratory.pk}),
        )

    @override_config(ENABLE_LABS=True)
    def test_report_detail_links_laboratory_when_flag_enabled(self) -> None:
        """The report detail links to the laboratory when on."""
        laboratory = factories.LaboratoryFactory()
        report = factories.ReportFactory(laboratory=laboratory)
        response = self.client.get(
            reverse("apps.reports:report_detail", kwargs={"pk": report.pk})
        )
        self.assertContains(
            response,
            reverse("apps.reports:laboratory_detail", kwargs={"pk": laboratory.pk}),
        )
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: FAIL en `test_report_detail_disables_laboratory_link_when_flag_disabled`.

- [ ] **Step 3: Edita `templates/reports/report/detail.html`**

Sustituye el `<dd>` del laboratorio (líneas ~54-58) por:

```django
                <dd class="mt-1 text-sm font-semibold text-black dark:text-white">
                    {% if report.laboratory %}
                    {% if config.ENABLE_LABS %}
                    <a href="{% url 'apps.reports:laboratory_detail' report.laboratory.pk %}" class="text-primary hover:underline">{{ report.laboratory.name }}</a>
                    {% else %}
                    <span>{{ report.laboratory.name }}</span>
                    {% endif %}
                    {% else %}—{% endif %}
                </dd>
```

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/reports/report/detail.html apps/reports/tests/test_templates.py
git commit -m "feat(reports): disable laboratory link in report detail behind feature flag"
```

---

## Task 7: Export de informes (filtro)

**Files:**
- Modify: `templates/reports/report/export.html` (~líneas 38-41)
- Test: `apps/reports/tests/test_templates.py`

**Interfaces:**
- Consumes: `{{ config.ENABLE_LABS }}`.
- Produces: sin `name="laboratory"` en el formulario de export cuando el flag está apagado. El grid `md:grid-cols-12` refluye sin huecos fijos.

- [ ] **Step 1: Escribe los tests que fallan**

```python
class ReportExportFlagTests(TestCase):
    """The export laboratory filter is gated by the flag."""

    @override_config(ENABLE_LABS=False)
    def test_export_hides_laboratory_filter_when_flag_disabled(self) -> None:
        """The export page hides the laboratory filter when off."""
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertNotContains(response, 'name="laboratory"')

    @override_config(ENABLE_LABS=True)
    def test_export_shows_laboratory_filter_when_flag_enabled(self) -> None:
        """The export page shows the laboratory filter when on."""
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertContains(response, 'name="laboratory"')
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: FAIL en los tests nuevos.

- [ ] **Step 3: Edita `templates/reports/report/export.html`**

Envuelve el `<div class="md:col-span-3">` que contiene `filter.form.laboratory` (líneas ~38-41) con `{% if config.ENABLE_LABS %}...{% endif %}`. El bloque de botones (`md:col-span-3`) se reubica automáticamente al fluir la rejilla; no se requieren cambios adicionales.

- [ ] **Step 4: Ejecuta y verifica que pasan**

Run: `uv run python manage.py test apps.reports.tests.test_templates`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/reports/report/export.html apps/reports/tests/test_templates.py
git commit -m "feat(reports): hide laboratory filter in report export behind feature flag"
```

---

## Task 8: i18n, limpieza y revisión (django-reviewer)

**Files:**
- Modify: `locale/es/LC_MESSAGES/django.po` (+ `.mo`) y `locale/en/LC_MESSAGES/django.po`

**Interfaces:**
- Consumes: la etiqueta `_("Enable laboratory management")` (Task 1).
- Produces: traducción al español compilada.

- [ ] **Step 1: Actualiza los catálogos**

Run:
```bash
uv run python manage.py makemessages -l es -l en
```

Añade la traducción en `locale/es/LC_MESSAGES/django.po`:

```po
msgid "Enable laboratory management"
msgstr "Habilitar gestión de laboratorios"
```

Compila:
```bash
uv run python manage.py compilemessages
```
Expected: se regenera `locale/es/LC_MESSAGES/django.mo`.

- [ ] **Step 2: Limpieza de código sin uso**

Revisa el diff completo (`git diff`) y elimina:
- Cualquier markup o clase de rejilla huérfana que hubiera quedado en las plantillas modificadas.
- Imports sin uso en `apps/reports/forms.py` y `apps/reports/filtersets.py` (verifícalo con `ruff`).

No elimines vistas, URLs, plantillas, `LaboratoryForm`, `LaboratoryFilter`, `LaboratoryFactory` ni la columna "Laboratorio" de `apps/reports/services/report_export.py`: los laboratorios siguen siendo un modelo válido y sus rutas siguen activas.

- [ ] **Step 3: Ejecuta toda la suite de las apps tocadas**

Run:
```bash
uv run python manage.py test apps.reports apps.equipment apps.dashboard apps.alerts
```
Expected: PASS (0 fallos).

- [ ] **Step 4: Lint**

Run:
```bash
uv run ruff check apps/reports config/settings/tools/django_constance.py
```
Expected: `All checks passed!`.

- [ ] **Step 5: Revisión con `django-reviewer`**

Invoca el skill `django-reviewer` sobre el diff generado (`apps/reports/*`, `templates/reports/*`, `templates/includes/aside.html`, `config/settings/tools/django_constance.py`). Reporta hallazgos; aplica solo refinamientos elegibles que no cambien comportamiento. Vuelve a ejecutar Steps 3-4 tras cualquier edición.

- [ ] **Step 6: Commit**

```bash
git add locale/ apps/reports config/settings/tools/django_constance.py templates/
git commit -m "chore(reports): translate laboratory flag and clean up unused code"
```

---

## Criterios de aceptación

- [ ] `ENABLE_LABS` es editable en el admin de Constance y por defecto es `False`.
- [ ] Flag apagado: sin ítem de menú "Laboratories", sin encabezado "Informes" huérfano, sin campo de laboratorio en el formulario de informe, sin filtro de laboratorio en listado ni export, sin columna "Laboratorio" en el listado, y el enlace de laboratorio del detalle queda como texto plano. Rejillas balanceadas (12 columnas).
- [ ] Flag apagado: guardar un informe con laboratorio existente conserva su laboratorio.
- [ ] Flag apagado: `/laboratories/...` sigue respondiendo (rutas activas).
- [ ] Un usuario con solo `view_component_analysis` ve el encabezado "Informes" (fix del punto 1).
- [ ] Flag encendido: toda la UI de laboratorio vuelve exactamente como hoy.
- [ ] Suite de `reports`, `equipment`, `dashboard` y `alerts` en verde; `ruff` limpio; revisión `django-reviewer` aplicada.
