# Diseno: gestion de equipos a nombre de los clientes hijos (atribucion)

- **Fecha:** 2026-10-17
- **Estado:** Aprobado
- **Alcance:** Que laboratorio, intermedio y plataforma puedan **ver de quien es**
  cada sucursal, maquina y tipo de componente (columna + filtro), y **crearlos o
  editarlos a nombre de** cualquier organizacion de su sub-arbol.
- **Idioma:** UI en espanol via `{% trans %}` / `_()`; codigo, comentarios y
  docstrings en ingles (AGENTS.md).

## 1. Objetivo

Hoy la plataforma ya aisla los datos por organizacion y ya deja **ver** hacia
abajo (un laboratorio ve todo su tenant; un intermedio ve su sub-arbol). Pero en
la practica no se puede trabajar con eso:

- Al crear, `UserStampMixin` fuerza `organization = user.organization`, asi que
  el intermedio no puede dar de alta una sucursal, maquina o tipo de componente
  **dentro de** su cliente hijo.
- Los listados no muestran de quien es cada registro ni permiten filtrar por
  cliente, asi que con varios clientes debajo todo se ve mezclado.

El objetivo es cerrar las dos brechas: **atribucion** (ver y separar) y
**actuacion a nombre de** (crear/editar en el cliente correcto), reutilizando el
scoping que ya existe.

## 2. Contexto actual (hallazgos)

- `apps/organizations/models.py::Organization` es el arbol de tenancy
  (`parent` auto-referente, `kind` = platform/lab/intermediary/final,
  `descendants(include_self)`).
- `apps/organizations/scoping.py`:
  - `user_visible_organization_ids(user)` -> `None` (sin restriccion: superuser,
    org `PLATFORM`, usuario sin organizacion) o el conjunto de ids del sub-arbol.
  - `scope_queryset(queryset, user, field="organization")` -> filtra si el modelo
    tiene el campo.
  - `scope_choices(filterset, mapping)` -> reasigna querysets de
    `ModelChoiceFilter` (no-op sin `request`).
- `apps/core/mixins/views.py` scopea `BaseListView` / `BaseDetailView` /
  `BaseUpdateView` / `BaseDeleteView` por el campo `organization` (o
  `tenant_field`).
- `apps/core/mixins/forms.py::UserStampMixin` asigna la organizacion al crear,
  **solo si la instancia no trae una** (`if instance.organization_id is not
  None: return`). Por lo tanto, si el formulario fija la organizacion, el mixin
  **no la pisa**.
- `Branch`, `Machine`, `ComponentType` tienen FK `organization` (nullable).
  `Machine` ademas tiene `branch` y `fleet`.
- Los formularios `BranchForm`, `MachineForm`, `ComponentTypeForm` **no**
  exponen `organization`. Los `FilterSet` de los tres listados tampoco.
- La data existente **ya fue** backfilleada a MARCO por
  `apps/organizations/migrations/0002_seed_marco_tenant.py` y
  `apps/equipment/migrations/0004_assign_componenttype_organization.py`; no hace
  falta una migracion de datos nueva.
- `templates/users/account/list.html` ya muestra `account.user.organization.name`
  como badge: es el precedente visual de la columna "Cliente".
- `templates/includes/form_fields.html` recorre `{% for field in form %}`, asi que
  un campo nuevo en el formulario se renderiza solo.

## 3. Decisiones acordadas

| Tema | Decision |
|------|----------|
| Quien gestiona | Laboratorio, intermedio y plataforma gestionan (ver, filtrar, crear, editar, borrar) el sub-arbol completo. Los clientes finales conservan su comportamiento actual. |
| Clientes | Ya existen: **no** se construye alta de organizaciones cliente. |
| Alcance de entidades | `Branch`, `Machine`, `ComponentType`. Flota (`Fleet`) queda fuera. |
| Columnas/filtros | La columna y el filtro "Cliente" aparecen solo cuando el usuario puede elegir entre **mas de una** organizacion (intermedio/lab/plataforma). Para un cliente final la vista no cambia. |
| Campo "Cliente" en formularios | Opcional. Vacio = "sin cambio" en edicion y "mi organizacion" en alta (lo resuelve `UserStampMixin`). |
| Maquina | `Machine.organization` manda; si hay `branch`, deben pertenecer al mismo cliente. Sin `organization` y con `branch`, la organizacion se toma de la sucursal. |
| Tipos de componente | El intermedio puede crear un tipo a nombre de un hijo (propiedad del hijo) o en su propio nivel (visible a todos sus hijos). Sin reglas extra. |
| Migracion de datos | Innecesaria (ver hallazgos). |

## 4. Scoping: helpers nuevos

En `apps/organizations/scoping.py`:

- `visible_organizations(user) -> QuerySet`: el queryset de `Organization` que el
  usuario puede usar. `None` (sin restriccion) -> todas; si no, su sub-arbol.
- `is_organization_visible(user, organization) -> bool`: valida una organizacion
  concreta (defensa ante POST manipulado).
- `can_choose_organization(user) -> bool`: `True` si el usuario no tiene
  restriccion o ve mas de una organizacion. Es el unico predicado que decide si
  se muestra columna, filtro y campo.
- `scope_organization_filter(filterset, name="organization") -> None`: ajusta
  (o elimina) el filtro de organizacion de un `FilterSet` segun el `request`.
  No-op sin `request` (uso directo en tests).

## 5. Formularios

Nuevo mixin `OrganizationScopeFormMixin` en `apps/core/mixins/forms.py`:

- `__init__(self, *args, user=None, **kwargs)`: guarda `self.user`. Si el
  formulario tiene un campo `organization`:
  - `user is None` o `not can_choose_organization(user)` -> **quita** el campo
    (vuelve al comportamiento de hoy y evita borrar la organizacion actual, ya
    que sin campo la clave no entra en `cleaned_data`).
  - si el usuario puede elegir -> `queryset = visible_organizations(user)`,
    `label = _("Client")`, `empty_label = _("Own organization")`.
- `clean_organization()`: rechaza una organizacion no visible.
- `clean()`: si el campo existe y viene vacio, preserva
  `self.instance.organization` (vacio = "sin cambio", nunca borra al dueño).

Se aplica a `BranchForm`, `MachineForm` y `ComponentTypeForm`. `Meta.fields` de
cada uno incorpora `"organization"` (necesario para que `construct_instance`
guarde el valor) en primera posicion.

`MachineForm.clean()`/`clean_*`: coherencia organizacion/sucursal descrita en las
decisiones.

Las vistas `BranchCreateView`/`BranchUpdateView` y
`ComponentTypeCreateView`/`ComponentTypeUpdateView` pasan `user` al formulario
(como ya hace `MachineCreateView`).

## 6. Listados: columna y filtro

- Nuevo mixin de vista `ClientAttributionMixin` en `apps/core/mixins/views.py`:
  - `get_queryset()` -> añade `select_related("organization")`.
  - `get_context_data()` -> añade `show_organization` (via
    `can_choose_organization`).
- `MachineListView`, `BranchListView` y `ComponentTypeListView` lo usan.
- En cada `FilterSet` se declara `organization = ModelChoiceFilter(label=...,
  empty_label=_("All Clients"))` y `__init__` llama a
  `scoping.scope_organization_filter(self)`.

## 7. Plantillas

- `templates/equipment/machine/list.html`: columna "Cliente" (badge) y filtro
  condicionados por `show_organization`; la columna `Machine` pasa de `col-span-4`
  a `col-span-2` cuando aparece la de cliente (la suma sigue siendo 12 en las
  cuatro combinaciones con/sin flota).
- `templates/equipment/branch/list.html` y
  `templates/equipment/component_type/list.html`: columna "Cliente" y filtro
  (layout flex, se añade un hijo mas); la primera columna pasa de `col-span-4` a
  `col-span-2`.
- Detalles (`machine`, `branch`, `component_type`): fila "Cliente" en el bloque de
  informacion, condicionada por `show_organization`. Las vistas de detalle añaden
  `show_organization` al contexto.

## 8. Pruebas (meta 85 %)

- `apps/organizations/tests/test_scoping.py`: `visible_organizations`,
  `is_organization_visible`, `can_choose_organization` (sub-arbol, sin
  restriccion, anonimo, hoja).
- `apps/equipment/tests/test_client_attribution.py` (nuevo): formularios (campo
  visible/oculto, queryset scopado, POST con organizacion ajena rechazado, vacio
  preserva al dueño, coherencia maquina/sucursal), filtrosets (filtra por cliente,
  se oculta para hoja), vistas (crear para un hijo queda con la organizacion del
  hijo; `show_organization` correcto), plantillas (columna y filtro presentes para
  intermedio, ausentes para cliente final).
- Regresion: la suite de `equipment` sigue verde.

## 9. Fuera de alcance

- Alta de organizaciones cliente desde la aplicacion.
- Gestion de usuarios/cuentas a nombre de un hijo (mismo patron, se puede
  reutilizar despues).
- Flota (`Fleet`).
- Facturacion, limites de uso.
