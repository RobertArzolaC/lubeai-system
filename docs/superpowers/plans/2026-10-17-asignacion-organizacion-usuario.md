# Asignacion de organizacion a usuarios — Plan de implementacion

> **Para el agente implementador:** SUB-SKILL REQUERIDO: usa `superpowers:executing-plans` (ejecucion nativa) o `superpowers:subagent-driven-development` (tarea por tarea con revisor). Los pasos usan casillas (`- [ ]`).

**Goal:** Que la organizacion de un usuario se pueda **ver y fijar desde el admin de Django**, acotando las opciones al sub-arbol de organizaciones del usuario que edita.

**Architecture:** No se agregan modelos, servicios ni vistas. Se configura `CustomUserAdmin` para exponer el FK `User.organization` en el alta y el cambio (fieldsets, columnas, filtro) y se acota su queryset con el helper de tenancy ya existente `apps/organizations/scoping.py::visible_organizations`. La regla de negocio ("que organizaciones puede asignar un actor") queda centralizada en `scoping`, que ya es el unico lugar donde vive esa logica.

**Tech Stack:** Django 6.0, django-allauth 65, admin de Django, tests con `unittest` (Django `TestCase`) y `factory_boy`.

**Spec:** Conversacion (cambio pequeño; sin documento de diseno aparte).

## Global Constraints

- Codigo, comentarios y docstrings en **ingles**; plan y comunicacion en espanol (AGENTS.md).
- Tipado y docstrings PEP 257 en cada funcion/clase que se modifique; mantener comentarios existentes.
- **No** tocar modelos ni migraciones.
- **No** cambiar `scoping.py`: la regla "usuario sin organizacion = sin restriccion" es una decision documentada y queda intacta.
- **No** cambiar `CustomUserCreationForm.Meta.fields` ni `CustomUserChangeForm.Meta.fields`: `apps/users/tests/test_forms.py` afirma `== ("email",)` y no debe romperse.
- No anadir dependencias.
- Tests: `uv run python manage.py test <target> --settings=config.settings.testing`.
- Lint: `uv run ruff check <paths>` y `uv run ruff format <paths>`.
- Nota de entorno: `*.mo` no esta versionado; ya estan copiados a `locale/es/LC_MESSAGES/` y `locale/en/LC_MESSAGES/` en este worktree para que la suite completa pase. No borrarlos.

## Review Focus

1. **Alta en el admin sin elegir organizacion:** el usuario se guarda con `organization=None` (el modelo lo permite); la pagina no debe fallar.
2. **Cambio en el admin eligiendo una organizacion:** el valor se persiste y la pagina responde con redirect (302).
3. **Staff de una organizacion hoja:** el selector solo muestra su propia organizacion; no ve organizaciones ajenas.
4. **Staff con sub-arbol:** el selector muestra su organizacion y sus descendientes, no las de otra rama.
5. **Superusuario / usuario sin organizacion:** el selector muestra todas las organizaciones (sin restriccion).

---

## File Structure

- **Modify** `apps/users/admin.py` — exponer `organization` en el admin y acotar su queryset.
- **Create** `apps/users/tests/test_admin.py` — tests del admin (no existe hoy ningun test de admin en el proyecto).

---

## Task 1: El admin expone la organizacion del usuario

**Files:**
- Modify: `apps/users/admin.py`
- Test: `apps/users/tests/test_admin.py`

**Interfaces:**
- Produces:
  - `CustomUserAdmin.list_display: tuple[str, ...]` incluye `"organization"`.
  - `CustomUserAdmin.list_filter: tuple[str, ...]` incluye `"organization"`.
  - `CustomUserAdmin.fieldsets` (cambio) y `CustomUserAdmin.add_fieldsets` (alta) incluyen el campo `organization`, por lo que
    `CustomUserAdmin.get_form(request, obj)` expone `organization` en `base_fields` tanto con `obj=None` (alta) como con `obj=<user>` (cambio).

- [ ] **Step 1: Escribe los tests que fallan** en `apps/users/tests/test_admin.py`

```python
"""Tests for the user admin organization assignment."""

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.organizations import factories as org_factories
from apps.users import admin as users_admin
from apps.users import models as users_models
from apps.users.factories import UserFactory


class UserAdminOrganizationFieldTests(TestCase):
    """The admin exposes the ``organization`` field on add and change forms."""

    def setUp(self) -> None:
        """Build a model admin and an admin request."""
        self.site = AdminSite()
        self.model_admin = users_admin.CustomUserAdmin(users_models.User, self.site)
        self.request = RequestFactory().get("/admin/users/user/")
        self.request.user = UserFactory(is_staff=True, is_superuser=True)

    def test_change_form_exposes_organization(self) -> None:
        """The change form includes the organization field."""
        target = UserFactory()
        form_class = self.model_admin.get_form(self.request, obj=target)
        self.assertIn("organization", form_class.base_fields)

    def test_add_form_exposes_organization(self) -> None:
        """The add form includes the organization field."""
        form_class = self.model_admin.get_form(self.request)
        self.assertIn("organization", form_class.base_fields)

    def test_add_form_organization_is_optional(self) -> None:
        """Leaving the organization empty is allowed."""
        form_class = self.model_admin.get_form(self.request)
        self.assertFalse(form_class.base_fields["organization"].required)

    def test_changelist_shows_organization(self) -> None:
        """The changelist lists and filters by organization."""
        self.assertIn("organization", self.model_admin.list_display)
        self.assertIn("organization", self.model_admin.list_filter)


class UserAdminOrganizationSaveTests(TestCase):
    """Saving through the admin persists the organization."""

    def setUp(self) -> None:
        """Log an admin in and build a target organization."""
        self.admin = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.organization = org_factories.OrganizationFactory(slug="adm-save")

    def test_add_view_assigns_organization(self) -> None:
        """An add persists the selected organization."""
        response = self.client.post(
            reverse("admin:users_user_add"),
            {
                "email": "withorg@example.com",
                "password1": "Sup3rSecret!42",
                "password2": "Sup3rSecret!42",
                "is_active": "on",
                "organization": self.organization.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        user = users_models.User.objects.get(email="withorg@example.com")
        self.assertEqual(user.organization, self.organization)

    def test_change_view_assigns_organization(self) -> None:
        """A change persists the selected organization."""
        target = UserFactory()
        response = self.client.post(
            reverse("admin:users_user_change", args=[target.pk]),
            {
                "email": target.email,
                "is_active": "on",
                "organization": self.organization.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.organization, self.organization)
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `uv run python manage.py test apps.users.tests.test_admin --settings=config.settings.testing`
Expected: FAIL. `organization` no esta en `base_fields` ni en `list_display`/`list_filter`; los POST no envian el campo (no existe).

- [ ] **Step 3: Implementa**

En `apps/users/admin.py`, dentro de `CustomUserAdmin`:

1. Insertar `"organization"` en `list_display` despues de `"last_name"`.
2. Agregar `"organization"` a `list_filter` (queda `("is_active", "is_staff", "organization")`).
3. Insertar un bloque nuevo en `fieldsets`, entre `"Personal info"` y `"Permissions"`:

```python
        (
            "Organization",
            {"fields": ("organization",)},
        ),
```

4. Agregar `"organization"` a `add_fieldsets`, despues de `"is_active"`.

- [ ] **Step 4: Corre los tests y verifica que pasan**

Run: `uv run python manage.py test apps.users.tests.test_admin --settings=config.settings.testing`
Expected: PASS (6 tests).

- [ ] **Step 5: Verifica que Django no reporta problemas de admin**

Run: `uv run python manage.py check --settings=config.settings.testing`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Commit**

```bash
git add apps/users/admin.py apps/users/tests/test_admin.py
git commit -m "feat(users): expose organization field in the user admin"
```

---

## Task 2: Acotar las organizaciones asignables al sub-arbol del actor

**Files:**
- Modify: `apps/users/admin.py`
- Test: `apps/users/tests/test_admin.py`

**Interfaces:**
- Consumes: `apps.organizations.scoping.visible_organizations(user) -> QuerySet[Organization]`
- Produces: `CustomUserAdmin.formfield_for_foreignkey(db_field, request, **kwargs) -> forms.Field` que devuelve, para el campo `organization`, un `ModelChoiceField` cuyo `queryset` es `scoping.visible_organizations(request.user)`.

- [ ] **Step 1: Escribe los tests que fallan** en `apps/users/tests/test_admin.py`

```python
class UserAdminOrganizationScopeTests(TestCase):
    """The assignable organizations follow the acting user subtree."""

    def setUp(self) -> None:
        """Build a model admin and the tenant tree."""
        self.site = AdminSite()
        self.model_admin = users_admin.CustomUserAdmin(users_models.User, self.site)
        self.tenant = org_factories.OrganizationFactory(
            slug="adm-tenant", kind=org_choices.OrganizationKind.LAB
        )
        self.child = org_factories.OrganizationFactory(
            slug="adm-child",
            kind=org_choices.OrganizationKind.FINAL,
            parent=self.tenant,
        )
        self.outsider = org_factories.OrganizationFactory(
            slug="adm-outsider", kind=org_choices.OrganizationKind.LAB
        )

    def field_organization_ids(self, user) -> set[int]:
        """Return the organization ids offered by the admin field."""
        request = RequestFactory().get("/admin/users/user/")
        request.user = user
        field = self.model_admin.formfield_for_foreignkey(
            users_models.User._meta.get_field("organization"), request
        )
        return set(field.queryset.values_list("id", flat=True))

    def test_scoped_staff_sees_only_its_subtree(self) -> None:
        """A staff user with an organization sees it and its descendants."""
        staff = UserFactory(is_staff=True, organization=self.tenant)
        self.assertEqual(
            self.field_organization_ids(staff), {self.tenant.id, self.child.id}
        )

    def test_superuser_sees_every_organization(self) -> None:
        """A superuser is unrestricted."""
        admin = UserFactory(is_staff=True, is_superuser=True)
        ids = self.field_organization_ids(admin)
        self.assertIn(self.outsider.id, ids)
        self.assertIn(self.tenant.id, ids)
```

Nota: agregar `from apps.organizations import choices as org_choices` al encabezado del archivo.

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `uv run python manage.py test apps.users.tests.test_admin.UserAdminOrganizationScopeTests --settings=config.settings.testing`
Expected: FAIL en `test_scoped_staff_sees_only_its_subtree` (hoy el queryset es "todas las organizaciones" e incluye `adm-outsider`).

- [ ] **Step 3: Implementa**

En `apps/users/admin.py`:

1. Agregar imports:

```python
from django import forms

from apps.organizations import scoping
```

2. Agregar el metodo en `CustomUserAdmin`:

```python
    def formfield_for_foreignkey(self, db_field, request, **kwargs) -> forms.Field:
        """Scope the assignable organizations to the actor's subtree."""
        if db_field.name == "organization":
            kwargs["queryset"] = scoping.visible_organizations(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
```

- [ ] **Step 4: Corre los tests y verifica que pasan**

Run: `uv run python manage.py test apps.users.tests.test_admin --settings=config.settings.testing`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint y suite de los modulos tocados**

Run:
```bash
uv run ruff check apps/users/admin.py apps/users/tests/test_admin.py
uv run ruff format --check apps/users/admin.py apps/users/tests/test_admin.py
uv run python manage.py test apps.users apps.organizations apps.core --settings=config.settings.testing
```
Expected: ruff sin hallazgos; tests `OK`.

- [ ] **Step 6: Commit**

```bash
git add apps/users/admin.py apps/users/tests/test_admin.py
git commit -m "feat(users): scope assignable organizations to the actor subtree"
```

---

## Fuera de alcance (decidido en esta iteracion)

- **Selector de organizacion en el alta de cuentas (`AccountCreationForm`)**: no se incluye porque el POST de `apps.users:account_create` ya esta roto hoy. `AccountCreationForm` es un `Form` plano (sin `.instance`) pero `AccountCreateView` hereda `UserStampMixin` → `CreateView`: `AccountCreateView.form_valid` llama `form.save(self.request)` y luego `super().form_valid(form)`, que pasa por `UserStampMixin.form_valid` (`form.instance` → `AttributeError`) y por `ModelFormMixin.form_valid` (`form.save()` sin `request`). Requiere decidir primero el arreglo de ese flujo.
- **Endurecer la regla "usuario sin organizacion = sin restriccion"** (`scoping.py`): es una decision documentada con su costo anotado; cambiarla altera la semantica de seguridad y afectaria datos/pruebas existentes. Requiere aprobacion explicita.
