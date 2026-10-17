# Atribucion de clientes en equipos (sucursales, maquinas y tipos) — Plan de implementacion

> **Para el agente implementador:** SUB-SKILL REQUERIDO: usa `superpowers:executing-plans` (ejecucion nativa) o `superpowers:subagent-driven-development` (tarea por tarea con revisor). Los pasos usan casillas (`- [ ]`).

**Goal:** Que laboratorio, intermedio y plataforma vean de quien es cada sucursal, maquina y tipo de componente (columna + filtro "Cliente") y puedan crearlos/editarlos a nombre de cualquier organizacion de su sub-arbol.

**Architecture:** Se reutiliza el scoping de tenancy existente (`apps/organizations/scoping.py`). Tres piezas nuevas y pequenas: helpers de visibilidad, un mixin de formulario que expone un campo `organization` scopado (vacio = sin cambio), y un mixin de vista que añade `select_related("organization")` + la bandera `show_organization` para condicionar columna, filtro y campo. `UserStampMixin` ya respeta una organizacion fijada por el formulario, asi que no se toca.

**Tech Stack:** Django 6.0, django-filter 26.1, plantillas Django + Tailwind (TailAdmin), tests con `unittest` (Django `TestCase`) y `factory_boy`.

**Spec:** `docs/superpowers/specs/2026-10-17-atribucion-clientes-equipos-design.md`

## Global Constraints

- Codigo, comentarios y docstrings en **ingles** (AGENTS.md). Plan y comunicacion en espanol.
- Tipado y docstrings PEP 257 en cada funcion/clase que se modifique; mantener comentarios existentes.
- No tocar modelos ni migraciones (la organizacion ya existe y esta backfilleada).
- No tocar `apps/alerts`, `apps/reports`, `apps/dashboard`.
- El comportamiento de un **cliente final** (hoja) no cambia: sin columna, sin filtro, sin campo "Cliente".
- **Regresion obligatoria:** los tests actuales de `apps/equipment` y `apps/organizations` deben seguir pasando tal cual. Las factories y los formularios instanciados **sin** `user` no deben cambiar de comportamiento.
- Tests: `unittest` + factories del proyecto. Comando: `uv run python manage.py test <target> --settings=config.settings.testing`.
- Lint: `uv run ruff check <paths>` y `uv run ruff format <paths>`.
- No añadir dependencias.

## Review Focus

1. **Edicion por un usuario con varios clientes, dejando "Cliente" vacio:** NO debe reasignar el registro a la organizacion del usuario; debe conservar el dueño actual (o la de la sucursal en `Machine`).
2. **POST con `organization` de otra rama:** debe ser invalido (formulario) y no debe crear nada.
3. **Cliente final (organizacion hoja) viendo su listado:** exactamente igual que hoy: sin columna "Cliente", sin filtro, sin campo en el formulario.
4. **`Machine` con `branch` de un cliente y `organization` de otro:** debe fallar la validacion; con solo `branch`, la organizacion se toma de la sucursal.
5. **Formulario instanciado sin `user`** (uso directo / tests): no aparece el campo y guardar no borra `organization`.

---

## File Structure

- **Modify** `apps/organizations/scoping.py` — `visible_organizations`, `is_organization_visible`, `can_choose_organization`, `scope_organization_filter`.
- **Modify** `apps/core/mixins/forms.py` — `OrganizationScopeFormMixin`.
- **Modify** `apps/core/mixins/views.py` — `ClientAttributionMixin`.
- **Modify** `apps/core/mixins/__init__.py` — exportar los dos mixins nuevos.
- **Modify** `apps/equipment/forms.py` — aplicar el mixin a `BranchForm`, `MachineForm`, `ComponentTypeForm`; coherencia maquina/sucursal.
- **Modify** `apps/equipment/filtersets.py` — filtro `organization` en los tres `FilterSet`.
- **Modify** `apps/equipment/views.py` — mixin en los tres listados; `user` en los formularios de sucursal/tipo; `show_organization` en los tres detalles.
- **Modify** `templates/equipment/machine/list.html`, `branch/list.html`, `component_type/list.html` — columna y filtro "Cliente".
- **Modify** `templates/equipment/machine/detail.html`, `branch/detail.html`, `component_type/detail.html` — fila "Cliente".
- **Create** `apps/equipment/tests/test_client_attribution.py` — tests de la funcionalidad.
- **Modify** `apps/organizations/tests/test_scoping.py` — tests de los helpers.
- **Modify** `locale/es/LC_MESSAGES/django.po` (y `.mo` si hay `msgfmt`) — traducciones nuevas.

---

## Task 1: Helpers de visibilidad de organizaciones

**Files:**
- Modify: `apps/organizations/scoping.py`
- Test: `apps/organizations/tests/test_scoping.py`

**Interfaces:**
- Produces:
  - `scoping.visible_organizations(user) -> QuerySet[Organization]`
  - `scoping.is_organization_visible(user, organization) -> bool`
  - `scoping.can_choose_organization(user) -> bool`
  - `scoping.scope_organization_filter(filterset, name: str = "organization") -> None`

- [ ] **Step 1: Escribe los tests que fallan** en `apps/organizations/tests/test_scoping.py`

```python
class VisibleOrganizationsTests(TestCase):
    """``visible_organizations``/``can_choose_organization`` follow the subtree."""

    def setUp(self) -> None:
        self.lab = factories.OrganizationFactory(slug="vo-lab", kind=choices.OrganizationKind.LAB)
        self.inter = factories.OrganizationFactory(
            slug="vo-inter", kind=choices.OrganizationKind.INTERMEDIARY, parent=self.lab
        )
        self.final = factories.OrganizationFactory(
            slug="vo-final", kind=choices.OrganizationKind.FINAL, parent=self.inter
        )

    def _user_for(self, organization):
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        return user

    def test_intermediary_sees_subtree(self) -> None:
        user = self._user_for(self.inter)
        ids = set(scoping.visible_organizations(user).values_list("id", flat=True))
        self.assertEqual(ids, {self.inter.id, self.final.id})
        self.assertTrue(scoping.can_choose_organization(user))

    def test_leaf_cannot_choose(self) -> None:
        user = self._user_for(self.final)
        ids = set(scoping.visible_organizations(user).values_list("id", flat=True))
        self.assertEqual(ids, {self.final.id})
        self.assertFalse(scoping.can_choose_organization(user))

    def test_unrestricted_user_sees_all(self) -> None:
        user = user_factories.UserFactory()
        self.assertIsNone(scoping.user_visible_organization_ids(user))
        self.assertTrue(scoping.can_choose_organization(user))

    def test_anonymous_cannot_choose(self) -> None:
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(scoping.can_choose_organization(AnonymousUser()))

    def test_is_organization_visible(self) -> None:
        user = self._user_for(self.inter)
        self.assertTrue(scoping.is_organization_visible(user, self.final))
        self.assertFalse(scoping.is_organization_visible(user, self.lab))
        self.assertFalse(scoping.is_organization_visible(user, None))
```

- [ ] **Step 2: Ejecuta y confirma el fallo**

Run: `uv run python manage.py test apps.organizations.tests.test_scoping --settings=config.settings.testing`
Expected: FAIL con `AttributeError: module 'apps.organizations.scoping' has no attribute 'visible_organizations'`.

- [ ] **Step 3: Implementa los helpers** en `apps/organizations/scoping.py`

Import local de modelos dentro de las funciones para no forzar la carga de modelos al importar `scoping` (lo importan mixins que se cargan temprano):

```python
def visible_organizations(user) -> QuerySet:
    """Return the organizations ``user`` may act upon."""
    from apps.organizations import models as organization_models

    queryset = organization_models.Organization.objects.all()
    visible_ids = user_visible_organization_ids(user)
    if visible_ids is None:
        return queryset
    return queryset.filter(pk__in=visible_ids)


def is_organization_visible(user, organization) -> bool:
    """Return ``True`` when ``user`` may act on ``organization``."""
    if organization is None:
        return False
    visible_ids = user_visible_organization_ids(user)
    if visible_ids is None:
        return True
    return organization.pk in visible_ids


def can_choose_organization(user) -> bool:
    """Return ``True`` when ``user`` may pick among several organizations."""
    visible_ids = user_visible_organization_ids(user)
    return visible_ids is None or len(visible_ids) > 1


def scope_organization_filter(filterset, name: str = "organization") -> None:
    """Scope (or drop) a FilterSet's organization filter for its request user."""
    if name not in filterset.filters:
        return
    request = getattr(filterset, "request", None)
    if request is None:
        return
    if not can_choose_organization(request.user):
        del filterset.filters[name]
        return
    filterset.filters[name].queryset = visible_organizations(request.user)
```

- [ ] **Step 4: Ejecuta y confirma el verde**

Run: `uv run python manage.py test apps.organizations.tests.test_scoping --settings=config.settings.testing`
Expected: OK (los tests nuevos y los existentes).

- [ ] **Step 5: Commit**

```bash
git add apps/organizations/scoping.py apps/organizations/tests/test_scoping.py
git commit -m "feat(organizations): add visible-organization scoping helpers"
```

---

## Task 2: Campo "Cliente" en los formularios

**Files:**
- Modify: `apps/core/mixins/forms.py`
- Modify: `apps/core/mixins/__init__.py`
- Modify: `apps/equipment/forms.py`
- Modify: `apps/equipment/views.py` (pasar `user` en sucursal y tipo)
- Test: `apps/equipment/tests/test_client_attribution.py`

**Interfaces:**
- Consumes: `scoping.visible_organizations`, `scoping.is_organization_visible`, `scoping.can_choose_organization` (Task 1).
- Produces:
  - `core_mixins.OrganizationScopeFormMixin` (mixin de `forms.ModelForm` con `__init__(..., user=None, ...)`).
  - `BranchForm`, `MachineForm`, `ComponentTypeForm` aceptan `user=` y guardan `organization`.

- [ ] **Step 1: Escribe los tests que fallan** en `apps/equipment/tests/test_client_attribution.py`

```python
"""Tests for client attribution on branches, machines and component types."""

from django.test import TestCase

from apps.equipment import forms
from apps.organizations import choices, factories as org_factories
from apps.users import factories as user_factories


def user_for(organization):
    """Return a persisted user belonging to ``organization``."""
    user = user_factories.UserFactory()
    user.organization = organization
    user.save(update_fields=["organization"])
    return user


class OrganizationFormFieldTests(TestCase):
    """The Client field is scoped and only shown when the user can choose."""

    def setUp(self) -> None:
        self.lab = org_factories.OrganizationFactory(slug="ff-lab", kind=choices.OrganizationKind.LAB)
        self.inter = org_factories.OrganizationFactory(
            slug="ff-inter", kind=choices.OrganizationKind.INTERMEDIARY, parent=self.lab
        )
        self.final = org_factories.OrganizationFactory(
            slug="ff-final", kind=choices.OrganizationKind.FINAL, parent=self.inter
        )

    def test_field_hidden_without_user(self) -> None:
        self.assertNotIn("organization", forms.ComponentTypeForm().fields)

    def test_field_hidden_for_leaf_user(self) -> None:
        form = forms.ComponentTypeForm(user=user_for(self.final))
        self.assertNotIn("organization", form.fields)

    def test_field_scoped_for_intermediary(self) -> None:
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(user=user)
        self.assertIn("organization", form.fields)
        ids = set(form.fields["organization"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.inter.id, self.final.id})

    def test_foreign_organization_is_rejected(self) -> None:
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(
            data={"organization": self.lab.pk, "name": "X", "is_active": True},
            user=user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("organization", form.errors)

    def test_selected_organization_is_saved(self) -> None:
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(
            data={"organization": self.final.pk, "name": "Tipo hijo", "is_active": True},
            user=user,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save().organization_id, self.final.id)

    def test_empty_organization_keeps_current_owner(self) -> None:
        owner = org_factories.OrganizationFactory(slug="ff-owner", kind=choices.OrganizationKind.FINAL)
        component_type = __import__("apps.equipment.factories", fromlist=["x"]).ComponentTypeFactory(
            organization=owner, name="Tipo"
        )
        user = user_for(self.inter)
        form = forms.ComponentTypeForm(
            data={"organization": "", "name": "Tipo renombrado", "is_active": True},
            instance=component_type,
            user=user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        component_type.refresh_from_db()
        self.assertEqual(component_type.organization_id, owner.id)
```

(Nota: importa las factories en la cabecera del archivo —`from apps.equipment import factories as equipment_factories`— en vez del `__import__` del ejemplo.)

- [ ] **Step 2: Ejecuta y confirma el fallo**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution --settings=config.settings.testing`
Expected: FAIL (`organization` no esta en los fields / `__init__` no acepta `user`).

- [ ] **Step 3: Implementa `OrganizationScopeFormMixin`** en `apps/core/mixins/forms.py`

```python
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.organizations import scoping


class OrganizationScopeFormMixin:
    """Expose a scoped ``organization`` field on tenant-owned model forms.

    The field is removed when the acting user cannot choose among several
    organizations (no ``user``, or a leaf organization): without the field the
    key never reaches ``cleaned_data``, so the current owner is preserved.
    """

    def __init__(self, *args, user=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.user = user
        field = self.fields.get("organization")
        if field is None:
            return
        if user is None or not scoping.can_choose_organization(user):
            self.fields.pop("organization")
            return
        field.queryset = scoping.visible_organizations(user)
        field.label = _("Client")
        field.empty_label = _("Own organization")

    def clean_organization(self):
        """Reject organizations outside the acting user's subtree."""
        organization = self.cleaned_data.get("organization")
        if organization is not None and not scoping.is_organization_visible(
            self.user, organization
        ):
            raise ValidationError(_("You cannot use that client."), code="invalid")
        return organization

    def clean(self):
        """Treat an empty selection as "no change" instead of a clear."""
        cleaned = super().clean()
        if "organization" in self.fields and not cleaned.get("organization"):
            cleaned["organization"] = getattr(self.instance, "organization", None)
        return cleaned
```

Exportalo en `apps/core/mixins/__init__.py` (`from apps.core.mixins.forms import OrganizationScopeFormMixin, UserStampMixin` y añadirlo a `__all__`).

- [ ] **Step 4: Aplica el mixin a los formularios** en `apps/equipment/forms.py`

- `BranchForm(OrganizationScopeFormMixin, forms.ModelForm)` — `Meta.fields` empieza por `"organization"`.
- `ComponentTypeForm(OrganizationScopeFormMixin, forms.ModelForm)` — `Meta.fields` empieza por `"organization"`.
- `MachineForm(OrganizationScopeFormMixin, forms.ModelForm)` — `Meta.fields` empieza por `"organization"`; su `__init__` pasa `user` al `super()`:

```python
class MachineForm(OrganizationScopeFormMixin, forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs) -> None:
        super().__init__(*args, user=user, **kwargs)
        if not config.ENABLE_FLEET:
            self.fields.pop("fleet", None)
        if user is not None:
            self.fields["branch"].queryset = scoping.scope_queryset(
                models.Branch.objects.filter(is_active=True), user
            )
            if "fleet" in self.fields:
                self.fields["fleet"].queryset = scoping.scope_queryset(
                    models.Fleet.objects.filter(is_active=True), user
                )
```

- `BranchForm` y `ComponentTypeForm` necesitan un `__init__` que acepte `user` y lo reenvie:

```python
    def __init__(self, *args, user=None, **kwargs) -> None:
        super().__init__(*args, user=user, **kwargs)
```

- [ ] **Step 5: Pasa `user` desde las vistas** en `apps/equipment/views.py`

En `BranchCreateView`, `BranchUpdateView`, `ComponentTypeCreateView`, `ComponentTypeUpdateView` añade:

```python
    def get_form_kwargs(self) -> dict:
        """Pass the acting user so the client choices are scoped."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs
```

- [ ] **Step 6: Ejecuta y confirma el verde**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution apps.equipment.tests.test_forms apps.equipment.tests.test_views --settings=config.settings.testing`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add apps/core/mixins apps/equipment/forms.py apps/equipment/views.py apps/equipment/tests/test_client_attribution.py
git commit -m "feat(equipment): let users create branches, machines and types for a client"
```

---

## Task 3: Coherencia maquina / sucursal

**Files:**
- Modify: `apps/equipment/forms.py` (`MachineForm.clean`)
- Test: `apps/equipment/tests/test_client_attribution.py`

**Interfaces:**
- Consumes: `MachineForm` (Task 2).
- Produces: `MachineForm` garantiza `machine.organization == machine.branch.organization`.

- [ ] **Step 1: Escribe los tests que fallan**

```python
class MachineClientCoherenceTests(TestCase):
    """A machine's branch must belong to the selected client."""

    def setUp(self) -> None:
        self.lab = org_factories.OrganizationFactory(slug="mc-lab", kind=choices.OrganizationKind.LAB)
        self.client_a = org_factories.OrganizationFactory(
            slug="mc-a", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.client_b = org_factories.OrganizationFactory(
            slug="mc-b", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.user = user_for(self.lab)
        self.branch_b = equipment_factories.BranchFactory(organization=self.client_b)

    def _machine_data(self, **overrides):
        data = {
            "organization": self.client_a.pk,
            "branch": "",
            "fleet": "",
            "name": "Maquina",
            "serial_number": "SN-1",
            "model": "M",
            "is_active": True,
        }
        data.update(overrides)
        return data

    def test_branch_of_another_client_is_rejected(self) -> None:
        form = forms.MachineForm(
            data=self._machine_data(branch=self.branch_b.pk), user=self.user
        )
        self.assertFalse(form.is_valid())
        self.assertIn("branch", form.errors)

    def test_organization_is_taken_from_the_branch(self) -> None:
        form = forms.MachineForm(
            data=self._machine_data(organization="", branch=self.branch_b.pk),
            user=self.user,
        )
        self.assertTrue(form.is_valid())
        machine = form.save()
        self.assertEqual(machine.organization_id, self.client_b.id)
```

- [ ] **Step 2: Ejecuta y confirma el fallo**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution --settings=config.settings.testing`
Expected: FAIL (el formulario es valido con sucursal de otro cliente / no toma la organizacion de la sucursal).

- [ ] **Step 3: Implementa `MachineForm.clean`**

```python
    def clean(self):
        """Keep the machine's client coherent with its branch's client."""
        cleaned = super().clean()
        organization = cleaned.get("organization") or getattr(
            self.instance, "organization", None
        )
        branch = cleaned.get("branch")
        if branch is None:
            return cleaned
        if organization is None:
            cleaned["organization"] = branch.organization
        elif branch.organization_id != organization.pk:
            self.add_error(
                "branch",
                _("The branch does not belong to the selected client."),
            )
        return cleaned
```

- [ ] **Step 4: Ejecuta y confirma el verde**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution apps.equipment.tests.test_forms apps.equipment.tests.test_views --settings=config.settings.testing`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add apps/equipment/forms.py apps/equipment/tests/test_client_attribution.py
git commit -m "feat(equipment): keep machine client coherent with its branch"
```

---

## Task 4: Filtro "Cliente" en los listados

**Files:**
- Modify: `apps/equipment/filtersets.py`
- Test: `apps/equipment/tests/test_client_attribution.py`

**Interfaces:**
- Consumes: `scoping.scope_organization_filter` (Task 1).
- Produces: `BranchFilter`, `MachineFilter`, `ComponentTypeFilter` aceptan `organization` (pk) y lo ocultan cuando el usuario no puede elegir.

- [ ] **Step 1: Escribe los tests que fallan**

```python
class ClientFilterTests(TestCase):
    """The list filters accept an organization and hide it for leaf users."""

    def setUp(self) -> None:
        self.lab = org_factories.OrganizationFactory(slug="cf-lab", kind=choices.OrganizationKind.LAB)
        self.client_a = org_factories.OrganizationFactory(
            slug="cf-a", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.client_b = org_factories.OrganizationFactory(
            slug="cf-b", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.branch_a = equipment_factories.BranchFactory(organization=self.client_a)
        self.branch_b = equipment_factories.BranchFactory(organization=self.client_b)
        self.user = user_for(self.lab)

    def test_branch_filter_by_organization(self) -> None:
        request = SimpleNamespace(user=self.user)
        filtered = filtersets.BranchFilter(
            {"organization": self.client_a.pk},
            queryset=models.Branch.objects.all(),
            request=request,
        ).qs
        self.assertEqual(list(filtered), [self.branch_a])

    def test_organization_filter_hidden_for_leaf(self) -> None:
        leaf = user_for(self.client_a)
        request = SimpleNamespace(user=leaf)
        filterset = filtersets.BranchFilter(queryset=models.Branch.objects.all(), request=request)
        self.assertNotIn("organization", filterset.filters)

    def test_organization_filter_choices_are_scoped(self) -> None:
        request = SimpleNamespace(user=self.user)
        filterset = filtersets.MachineFilter(queryset=models.Machine.objects.all(), request=request)
        ids = set(filterset.filters["organization"].queryset.values_list("id", flat=True))
        self.assertEqual(ids, {self.lab.id, self.client_a.id, self.client_b.id})
```

(Importa `SimpleNamespace` de `types`, `filtersets`, `models` y las factories.)

- [ ] **Step 2: Ejecuta y confirma el fallo**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution --settings=config.settings.testing`
Expected: FAIL (`organization` no es un filtro valido).

- [ ] **Step 3: Implementa el filtro** en `apps/equipment/filtersets.py`

Importa `from apps.organizations import models as organization_models`. En los tres `FilterSet` declara:

```python
    organization = django_filters.ModelChoiceFilter(
        queryset=organization_models.Organization.objects.all(),
        empty_label=_("All Clients"),
        label=_("Client"),
    )
```

y añade `"organization"` a `Meta.fields`. En el `__init__` de cada uno (creando `__init__` si no existe) llama a `scoping.scope_organization_filter(self)` despues de `super().__init__(*args, **kwargs)`.

- [ ] **Step 4: Ejecuta y confirma el verde**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution apps.equipment.tests.test_filtersets --settings=config.settings.testing`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add apps/equipment/filtersets.py apps/equipment/tests/test_client_attribution.py
git commit -m "feat(equipment): filter branches, machines and types by client"
```

---

## Task 5: Mixin de vista y contexto `show_organization`

**Files:**
- Modify: `apps/core/mixins/views.py`
- Modify: `apps/core/mixins/__init__.py`
- Modify: `apps/equipment/views.py`
- Test: `apps/equipment/tests/test_client_attribution.py`

**Interfaces:**
- Consumes: `scoping.can_choose_organization` (Task 1).
- Produces: `core_mixins.ClientAttributionMixin` (añade `select_related("organization")` y `context["show_organization"]`).

- [ ] **Step 1: Escribe los tests que fallan**

```python
class ClientListContextTests(TestCase):
    """The list views expose the organization join and the show flag."""

    def setUp(self) -> None:
        self.lab = org_factories.OrganizationFactory(slug="lc-lab", kind=choices.OrganizationKind.LAB)
        self.final = org_factories.OrganizationFactory(
            slug="lc-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )

    def test_machine_list_selects_organization(self) -> None:
        related = equipment_views.MachineListView().get_queryset().query.select_related
        self.assertIn("organization", related)

    def test_show_organization_flag(self) -> None:
        view = equipment_views.BranchListView()
        view.request = SimpleNamespace(user=user_for(self.lab))
        self.assertTrue(view.get_context_data()["show_organization"])
        view.request = SimpleNamespace(user=user_for(self.final))
        self.assertFalse(view.get_context_data()["show_organization"])
```

(`BranchListView.get_context_data()` necesita `self.object_list`/kwargs que `super()` pueda resolver; si el `ListView` pide `paginate_by` sin request, inicializa `view.request` como arriba y usa `view.kwargs = {}` si hiciera falta.)

- [ ] **Step 2: Ejecuta y confirma el fallo**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution --settings=config.settings.testing`
Expected: FAIL (`show_organization` no esta en el contexto / `organization` no esta en `select_related`).

- [ ] **Step 3: Implementa el mixin** en `apps/core/mixins/views.py`

```python
class ClientAttributionMixin:
    """Expose the owning organization in tenant-scoped list views.

    Adds the ``organization`` join to the queryset and a ``show_organization``
    context flag used by templates to render the "Client" column and filter only
    when the user can act on more than one organization.
    """

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().select_related("organization")

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        context["show_organization"] = scoping.can_choose_organization(
            scoping.request_user(getattr(self, "request", None))
        )
        return context
```

Exportalo en `apps/core/mixins/__init__.py`.

- [ ] **Step 4: Usa el mixin en las vistas** en `apps/equipment/views.py`

- `MachineListView(ClientAttributionMixin, core_mixins.BaseListView)`.
- `BranchListView(ClientAttributionMixin, core_mixins.BaseListView)`.
- `ComponentTypeListView(ClientAttributionMixin, core_mixins.BaseListView)`.
- En las tres vistas de detalle (`MachineDetailView`, `BranchDetailView`, `ComponentTypeDetailView`) añade `context["show_organization"] = scoping.can_choose_organization(self.request.user)`.

- [ ] **Step 5: Ejecuta y confirma el verde**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution apps.equipment.tests.test_views apps.equipment.tests.test_templates --settings=config.settings.testing`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add apps/core/mixins apps/equipment/views.py apps/equipment/tests/test_client_attribution.py
git commit -m "feat(equipment): expose client attribution in the list views"
```

---

## Task 6: Columna "Cliente" y fila en los detalles

**Files:**
- Modify: `templates/equipment/machine/list.html`
- Modify: `templates/equipment/branch/list.html`
- Modify: `templates/equipment/component_type/list.html`
- Modify: `templates/equipment/machine/detail.html`
- Modify: `templates/equipment/branch/detail.html`
- Modify: `templates/equipment/component_type/detail.html`
- Test: `apps/equipment/tests/test_client_attribution.py`

**Interfaces:**
- Consumes: `show_organization` (Task 5) y el filtro `organization` (Task 4).

- [ ] **Step 1: Escribe los tests que fallan**

```python
@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)  # la constante que ya usa test_views
class ClientColumnRenderingTests(TestCase):
    """The Client column and filter appear for parent users only."""

    def setUp(self) -> None:
        self.lab = org_factories.OrganizationFactory(slug="cr-lab", kind=choices.OrganizationKind.LAB)
        self.final = org_factories.OrganizationFactory(
            slug="cr-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        equipment_factories.BranchFactory(name="Sucursal Unica", organization=self.final)

    def test_intermediary_sees_column_and_filter(self) -> None:
        user = user_for(self.lab)
        grant_permissions(user, "view_branch")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.equipment:branch_list"))
        self.assertContains(response, 'name="organization"')
        self.assertContains(response, "Sucursal Unica")

    def test_leaf_does_not_see_column_or_filter(self) -> None:
        user = user_for(self.final)
        grant_permissions(user, "view_branch")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.equipment:branch_list"))
        self.assertNotContains(response, 'name="organization"')
```

- [ ] **Step 2: Ejecuta y confirma el fallo**

Run: `uv run python manage.py test apps.equipment.tests.test_client_attribution --settings=config.settings.testing`
Expected: FAIL (no aparece `name="organization"`).

- [ ] **Step 3: Edita las plantillas de listado**

En `templates/equipment/machine/list.html`:
- El filtro: envuelve un bloque con `{% if show_organization %}` y renderiza `{% render_field filter.form.organization ... %}`; ajusta los `md:col-span` de `name_search`, `branch` e `is_active` segun la tabla del spec (columna `Machine` `col-span-2` cuando `show_organization`).
- El encabezado y cada fila: la celda maquina pasa a `col-span-{% if show_organization %}2{% else %}4{% endif %}` y se añade, si `show_organization`, una celda `col-span-2` con `{{ machine.organization.name|default:"—" }}` (badge igual al de `templates/users/account/list.html`).

En `templates/equipment/branch/list.html` y `templates/equipment/component_type/list.html`:
- Añade el `<select>` de `filter.form.organization` dentro del formulario de filtros (`{% if show_organization %}`).
- La primera columna pasa de `col-span-4` a `col-span-{% if show_organization %}2{% else %}4{% endif %}` y se añade la celda de cliente `col-span-2` (encabezado + filas) cuando `show_organization`.

- [ ] **Step 4: Edita las plantillas de detalle**

En el bloque "Information" de `machine/detail.html`, `branch/detail.html` y
`component_type/detail.html` añade, con `{% if show_organization %}`:

```html
<div>
    <dt class="text-xs font-bold uppercase tracking-wider text-bodydark2">{% trans "Client" %}</dt>
    <dd class="mt-1 text-sm font-semibold text-black dark:text-white">{{ branch.organization.name|default:"—" }}</dd>
</div>
```

(cambia `branch` por la variable de cada plantilla: `machine` / `branch` / `component_type`).

- [ ] **Step 5: Ejecuta y confirma el verde**

Run: `uv run python manage.py test apps.equipment --settings=config.settings.testing`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add templates/equipment apps/equipment/tests/test_client_attribution.py
git commit -m "feat(equipment): show the client column and detail row"
```

---

## Task 7: Traducciones y cierre

**Files:**
- Modify: `locale/es/LC_MESSAGES/django.po` (+ `.mo` si hay `msgfmt`)

- [ ] **Step 1: Añade las traducciones** al `.po` para `Client`, `All Clients`, `Own organization`, `You cannot use that client.`, `The branch does not belong to the selected client.` (msgstr en espanol: "Cliente", "Todos los clientes", "Mi organizacion", "No puedes usar ese cliente.", "La sucursal no pertenece al cliente seleccionado.").

- [ ] **Step 2: Compila si hay gettext**

Run: `uv run python manage.py compilemessages -l es`
Expected: `processing file django.po` sin errores. Si `msgfmt` no esta instalado, deja el `.po` y anotalo.

- [ ] **Step 3: Lint y suite completa**

Run: `uv run ruff check apps && uv run ruff format --check apps`
Run: `uv run python manage.py test apps.equipment apps.organizations --settings=config.settings.testing`
Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add locale
git commit -m "chore(i18n): translate client attribution strings"
```
