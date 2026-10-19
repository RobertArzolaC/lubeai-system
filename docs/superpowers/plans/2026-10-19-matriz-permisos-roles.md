# Matriz de permisos de roles: alcance de dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `/users/roles/create/` y `/users/roles/<pk>/update/` muestren solo los permisos de los módulos del dashboard, agrupados por módulo y con etiquetas legibles en español.

**Architecture:** Se añade un catálogo explícito de app labels permitidos en `apps/users/constants.py`. `RoleForm` filtra el queryset de `auth.Permission` por ese catálogo —lo que además invalida cualquier POST fuera de alcance— y expone `permission_modules` agrupado módulo → modelo → permiso con etiquetas generadas. La plantilla pinta una sección por módulo, conserva las tarjetas por modelo y el "seleccionar todo" por modelo.

**Tech Stack:** Django 5, django-filter, widget-tweaks, Tailwind (TailAdmin), Django `TestCase` + factory_boy.

**Spec:** Conversación de diseño (2026-10-19). Decisiones aprobadas: (1) solo módulos del dashboard; (2) agrupación módulo + tarjetas por modelo; (3) etiquetas de permiso en español.

---

## Global Constraints

- All code, comments, docstrings and identifiers in **English**; user-facing strings wrapped in `gettext_lazy as _` / `{% trans %}`.
- **Type annotations + PEP 257 docstrings** on every function, class and test.
- Frontend: **TailAdmin + Tailwind** tokens only (`bg-primary`, `border-stroke`, `text-bodydark2`, `dark:` variants). No new fonts or color tokens.
- Tests are Django `TestCase` with `factory_boy`, in `apps/*/tests/`.
- Verification command (each task and the full suite):
  `docker compose exec -T django python manage.py test --settings=config.settings.testing <targets> -v 2`
- Coverage minimum: 85%.

## Review Focus

1. Un POST manipulado con permisos de `auth`, `admin` o terceros debe ser rechazado por el formulario, no solo ocultado en la plantilla → Task 1.
2. Un permiso personalizado (`view_component_analysis`, `acknowledge_alert`) no debe generar una etiqueta ambigua tipo "Ver Informe" duplicada; debe usar su nombre traducido → Task 1.
3. Un rol existente con permisos de sistema pierde esos permisos al guardarse desde la UI (no se renderizan ni se envían). Es el comportamiento buscado; se documenta para el revisor → Task 1.
4. Los módulos deben respetar el orden del dashboard, no el alfabético del app label → Task 2.
5. El "seleccionar todo" debe seguir funcionando con la estructura anidada módulo → modelo → permiso → Task 2.

---

### Task 1: Restringir el catálogo y traducir las etiquetas

**Files:**
- Create: `apps/users/constants.py`
- Modify: `apps/users/forms.py:35-118`
- Modify: `templates/users/role/_permission_matrix.html:15-22`
- Test: `apps/users/tests/test_forms.py`

**Interfaces:**
- Produces: `apps.users.constants.ROLE_PERMISSION_MODULES: dict[str, str]` — ordered mapping `app_label → translated module label`.
- Produces: `apps.users.constants.PERMISSION_ACTIONS: dict[str, str]` — `view/add/change/delete → Ver/Crear/Editar/Eliminar`.
- Produces: `RoleForm.permission_groups -> list[dict]` where each permission entry is `{"pk": int, "label": str}`.
- Produces: `RoleForm._permission_label(permission: Permission) -> str`.

- [x] **Step 1: Write the failing tests**

Append to `apps/users/tests/test_forms.py`:

```python
class RoleFormPermissionCatalogTests(UserTenantTestCase):
    """The role form only offers dashboard permissions with readable labels."""

    def setUp(self) -> None:
        super().setUp()
        self.organization = organization_factories.OrganizationFactory()
        self.user = UserFactory(organization=self.organization)
        self.form = users_forms.RoleForm(user=self.user)

    def test_only_dashboard_modules_are_offered(self) -> None:
        """The permission queryset is limited to the dashboard app labels."""
        app_labels = set(
            self.form.fields["permissions"].queryset.values_list(
                "content_type__app_label", flat=True
            )
        )
        self.assertEqual(app_labels, set(users_constants.ROLE_PERMISSION_MODULES))

    def test_system_permissions_are_rejected(self) -> None:
        """A tampered POST with an auth permission is invalid."""
        permission = Permission.objects.get(
            content_type__app_label="auth", codename="add_group"
        )
        form = users_forms.RoleForm(
            data={
                "organization": self.organization.pk,
                "name": "Analista",
                "description": "",
                "is_active": "on",
                "permissions": [permission.pk],
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("permissions", form.errors)

    def test_permission_labels_are_human_readable(self) -> None:
        """Standard and custom permissions get Spanish labels."""
        labels = [
            permission["label"]
            for group in self.form.permission_groups
            for permission in group["permissions"]
        ]
        self.assertIn("Ver Máquina", labels)
        self.assertIn("Puede ver el análisis de componentes", labels)
```

Imports to add at the top of the file:

```python
from django.contrib.auth.models import Permission

from apps.organizations import factories as organization_factories
from apps.users import constants as users_constants
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `docker compose exec -T django python manage.py test apps.users.tests.test_forms.RoleFormPermissionCatalogTests --settings=config.settings.testing -v 2`

Expected: FAIL — `apps.users.constants` does not exist / `RoleForm` has no attribute `permission_groups` entries with `label`.

- [x] **Step 3: Create the constants module**

`apps/users/constants.py`:

```python
"""Constants for the users app."""

from typing import Final

from django.utils.translation import gettext_lazy as _

ROLE_PERMISSION_MODULES: Final[dict[str, str]] = {
    "equipment": _("Equipment"),
    "reports": _("Reports"),
    "alerts": _("Alerts"),
    "organizations": _("Clients"),
    "users": _("Accounts and access"),
}

PERMISSION_ACTIONS: Final[dict[str, str]] = {
    "view": _("View"),
    "add": _("Create"),
    "change": _("Edit"),
    "delete": _("Delete"),
}
```

- [x] **Step 4: Filter the queryset and build readable labels in `RoleForm`**

In `apps/users/forms.py`:

- Import `gettext` and `capfirst`:

```python
from django.template.defaultfilters import capfirst
from django.utils.translation import gettext, gettext_lazy as _
```

- Import the constants: `from apps.users import constants, models, services`.
- Change the declared `permissions` field queryset to `Permission.objects.none()`.
- In `__init__`, after `super().__init__(...)`, assign:

```python
self.fields["permissions"].queryset = (
    Permission.objects.filter(
        content_type__app_label__in=constants.ROLE_PERMISSION_MODULES
    )
    .select_related("content_type")
    .order_by("content_type__app_label", "content_type__model", "codename")
)
```

- Add:

```python
def _permission_label(self, permission: Permission) -> str:
    """Return a readable Spanish label for ``permission``.

    Standard CRUD codenames are rendered as action + model; custom
    permissions fall back to their translated stored name.
    """
    action, _, _model = permission.codename.partition("_")
    action_label = constants.PERMISSION_ACTIONS.get(action)
    if action_label is not None and permission.codename == (
        f"{action}_{permission.content_type.model}"
    ):
        return f"{action_label} {capfirst(permission.content_type.name)}"
    return gettext(permission.name)
```

- In `permission_groups`, keep grouping by content type but replace the raw permission list:

```python
"permissions": [
    {"pk": permission.pk, "label": self._permission_label(permission)}
    for permission in permissions
],
```

- Use `capfirst(content_type.name)` for the group `label`.

- [x] **Step 5: Update the template to use the readable label**

In `templates/users/role/_permission_matrix.html`, replace `{{ permission.name }}` with `{{ permission.label }}`.

- [x] **Step 6: Run the tests to verify they pass**

Run: `docker compose exec -T django python manage.py test apps.users.tests.test_forms.RoleFormPermissionCatalogTests --settings=config.settings.testing -v 2`

Expected: PASS 3/3.

- [x] **Step 7: Commit**

```bash
git add apps/users/constants.py apps/users/forms.py templates/users/role/_permission_matrix.html apps/users/tests/test_forms.py
git commit -m "fix(users): scope role permissions to dashboard modules"
```

---

### Task 2: Agrupar la matriz por módulo

**Files:**
- Modify: `apps/users/forms.py` (add `permission_modules`)
- Modify: `templates/users/role/_permission_matrix.html`
- Modify: `locale/es/LC_MESSAGES/django.po` (new msgid + references)
- Generate (git-ignored): `locale/es/LC_MESSAGES/django.mo` (compiled at deploy time)
- Test: `apps/users/tests/test_role_views.py`

**Interfaces:**
- Consumes: `RoleForm.permission_groups` from Task 1.
- Produces: `RoleForm.permission_modules -> list[dict]` with shape
  `{"app_label": str, "label": str, "groups": list[dict]}`, in
  `ROLE_PERMISSION_MODULES` order.

- [x] **Step 1: Write the failing test**

Append to `apps/users/tests/test_role_views.py`:

```python
def test_create_renders_only_dashboard_permission_modules(self) -> None:
    """The matrix shows dashboard modules and no Django/third-party groups."""
    grant(self.user, "add_role")
    response = self.client.get(reverse("apps.users:role_create"))
    self.assertEqual(response.status_code, 200)
    for header in (
        "Equipos",
        "Informes",
        "Alertas",
        "Clientes",
        "Cuentas y accesos",
    ):
        self.assertContains(response, header)
    for system_header in (
        "Entrada de registro",
        "Tarea periódica",
        "Sesión",
        "Token",
        "Tipo de contenido",
    ):
        self.assertNotContains(response, system_header)
    self.assertContains(response, "Ver Máquina")
```

- [x] **Step 2: Run the test to verify it fails**

Run: `docker compose exec -T django python manage.py test apps.users.tests.test_role_views.RoleViewTests.test_create_renders_only_dashboard_permission_modules --settings=config.settings.testing -v 2`

Expected: FAIL — the module headers are not rendered and system groups still appear.

- [x] **Step 3: Add `permission_modules` to `RoleForm`**

In `apps/users/forms.py`:

```python
@property
def permission_modules(self) -> list[dict]:
    """Group the permission cards by dashboard module, in menu order."""
    groups = self.permission_groups
    return [
        {
            "app_label": app_label,
            "label": label,
            "groups": [group for group in groups if group["app_label"] == app_label],
        }
        for app_label, label in constants.ROLE_PERMISSION_MODULES.items()
        if any(group["app_label"] == app_label for group in groups)
    ]
```

- [x] **Step 4: Render module sections in the template**

Replace the outer grid of `templates/users/role/_permission_matrix.html` with one section per module. Keep the existing card markup inside. Use `group.key` (for example `equipment.machine`) as the value of `data-select-all` and `data-group`; update the script to select by that key:

```html
<div class="flex flex-col gap-8">
    {% for module in form.permission_modules %}
    <section>
        <div class="mb-4 flex items-center gap-3">
            <h4 class="text-lg font-bold text-black dark:text-white">{{ module.label }}</h4>
            <span class="h-px flex-1 bg-stroke dark:bg-strokedark" aria-hidden="true"></span>
        </div>
        <div class="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {% for group in module.groups %}
            <div class="flex flex-col rounded-xl border border-stroke bg-white dark:border-strokedark dark:bg-boxdark-2">
                <div class="flex items-center justify-between border-b border-stroke px-4 py-3 dark:border-strokedark">
                    <span class="text-sm font-bold text-black dark:text-white">{{ group.label }}</span>
                    <label class="flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-bodydark2 hover:text-primary">
                        <input type="checkbox" data-select-all="{{ group.key }}" class="h-4 w-4 rounded border-stroke text-primary focus:ring-primary" />
                        {% trans "All" %}
                    </label>
                </div>
                <div class="flex flex-col gap-2 p-4">
                    {% for permission in group.permissions %}
                    <label class="flex cursor-pointer items-center gap-2.5 text-sm text-black dark:text-white">
                        <input type="checkbox" name="permissions" value="{{ permission.pk }}"
                               data-group="{{ group.key }}"
                               class="h-4.5 w-4.5 rounded border-stroke text-primary focus:ring-primary"
                               {% if permission.pk|stringformat:"s" in form.selected_permission_ids %}checked{% endif %} />
                        <span>{{ permission.label }}</span>
                    </label>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
    </section>
    {% empty %}
    <p class="text-sm font-medium text-bodydark2">{% trans "No permissions available." %}</p>
    {% endfor %}
</div>
```

The script becomes:

```javascript
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-select-all]').forEach((toggle) => {
        const key = toggle.dataset.selectAll;
        const boxes = document.querySelectorAll(`input[data-group="${key}"]`);
        const sync = () => {
            const allChecked = boxes.length > 0 && Array.from(boxes).every((box) => box.checked);
            toggle.checked = allChecked;
        };
        toggle.addEventListener('change', () => {
            boxes.forEach((box) => { box.checked = toggle.checked; });
        });
        boxes.forEach((box) => box.addEventListener('change', sync));
        sync();
    });
});
```

- [x] **Step 5: Add the missing translation and compile it**

In `locale/es/LC_MESSAGES/django.po`, add:

```po
msgid "Accounts and access"
msgstr "Cuentas y accesos"
```

Compile:

```bash
docker compose exec -T django python manage.py compilemessages -l es
```

Expected: no output or `processing file ... django.po`; a newer `django.mo` timestamp.

- [x] **Step 6: Run the tests to verify they pass**

Run: `docker compose exec -T django python manage.py test apps.users.tests.test_forms.RoleFormPermissionCatalogTests apps.users.tests.test_role_views --settings=config.settings.testing -v 2`

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add apps/users/forms.py templates/users/role/_permission_matrix.html locale/es/LC_MESSAGES/django.po apps/users/tests/test_role_views.py
git commit -m "feat(users): group role permissions by dashboard module"
```

`django.mo` is ignored by `.gitignore` and is compiled by the deploy entrypoint
(`DJANGO_COMPILEMESSAGES=1`); only the `.po` is committed.

---

### Task 3: Verificación final

- [x] **Step 1: Run the full users suite**

Run: `docker compose exec -T django python manage.py test apps.users --settings=config.settings.testing -v 2`

Expected: PASS, 0 failures.

- [x] **Step 2: Run the full project suite**

Run: `docker compose exec -T django python manage.py test --settings=config.settings.testing -v 2`

Expected: PASS, 0 failures. Executed: 781/782 pass; the only failure is a pre-existing equipment template assertion documented in the execution notes below.

- [x] **Step 3: Inspect the rendered page**

Print the module/group/permission structure from a Django shell in the `marco` tenant, or open `/users/roles/create/` logged in as an admin:

- 5 modules: Equipos, Informes, Alertas, Clientes, Cuentas y accesos.
- 13 model cards, 54 permissions.
- No `Entrada de registro`, `Tarea periódica`, `Sesión`, `Token` or `Tipo de contenido`.

---

## Execution Notes (2026-10-19)

- **Targeted tests:** 11/11 pass (`RoleFormPermissionCatalogTests` + `RoleViewTests`).
- **Users suite:** 97/97 pass under `config.settings.testing`.
- **Full suite:** 781/782 pass. The single failure is pre-existing and unrelated to this plan:
  `apps.equipment.tests.test_templates.DashboardModuleAccessTests.test_dashboard_hides_equipment_links_without_permission`
  asserts that `/equipment/machines/` is absent from the dashboard response, but the
  dashboard's machine autocomplete renders `/equipment/machines/autocomplete/`, which
  contains that substring. The test fails in isolation on untouched equipment/dashboard
  code; it is left as a separate fix.
- **Rendered matrix in the `marco` tenant:** 5 modules (Equipos, Informes, Alertas,
  Clientes, Cuentas y accesos), 13 model cards, 54 permissions.
- **Test DB isolation:** the verification runs used `TEST.NAME=test_django_role_matrix`
  because another process was holding the shared `test_django` database.
