# Multi-tenant + branding por organizacion (MARCO) - Plan de implementacion

> **Para el agente implementador:** SUB-SKILL REQUERIDO: usa
> `superpowers:executing-plans` (ejecucion nativa) o
> `superpowers:subagent-driven-development`. Los pasos usan casillas (`- [ ]`).

**Goal:** Convertir la plataforma en multi-organizacion (tenant con jerarquia
intermediario/final), con aislamiento de datos, branding por organizacion y
capacidades por tipo, poblar datos historicos del laboratorio y eliminar el
codigo muerto.

**Architecture:** Nueva app `apps/organizations` con el modelo `Organization`
(auto-referencia, `kind`, branding, capabilities). FKs nullable de
`organization` en `equipment`/`reports`/`users`. Middleware resuelve el tenant
por subdominio (respaldo por slug). Context processor inyecta branding. Scoping
por sub-arbol aplicado en los mixins base y en los filtros/endpoints.

**Tech Stack:** Django 6.0, DRF, django-filter, django-constance, Tailwind
(TailAdmin), tests `unittest` + `factory_boy`, Postgres/Redis via docker.

**Spec:** `docs/superpowers/specs/2026-10-16-multi-tenant-marco-design.md`

## Global Constraints

- Codigo, comentarios y docstrings en **ingles**; UI en espanol via `{% trans %}`.
- Tipado y docstrings PEP 257 en cada funcion/clase nueva o modificada.
- FKs de organizacion **nullable**; nunca romper la data existente.
- Sin renombrar ni borrar modelos existentes en este plan.
- Pruebas: `unittest` + factories del proyecto. Comando:
  `docker compose exec django coverage run manage.py test --settings=config.settings.testing --noinput <target>`.
- Lint: `docker compose exec django ruff check <paths>` (o `uv run ruff check`).
- Reutilizar los mixins de `apps/core/mixins/` (no duplicar logica de vista).

## Review Focus

1. **Fuga entre tenants:** un usuario del tenant A nunca debe ver objetos del
   tenant B en listados, detalle, export, autocompletado ni API.
2. **Data legada:** la data existente (sin organizacion) debe quedar visible
   como MARCO y no romper listados/dashboards.
3. **Branding heredado:** si un intermediario define color/logo, sus finales
   deben heredarlo; si nadie define, caer a la marca por defecto sin errores.
4. **Login sin tenant resoluble:** en un host desconocido/desarrollo, el login
   debe renderizar con la marca por defecto sin excepcion.
5. **Capacidades:** con `ENABLE_LABS` global apagado la UI se comporta como hoy,
   aunque una organizacion tenga la capacidad encendida.

---

## File Structure

- **Create** `apps/organizations/` (app): `__init__.py`, `apps.py`, `models.py`,
  `choices.py`, `constants.py`, `services.py`, `scoping.py`, `middleware.py`,
  `context_processors.py`, `admin.py`, `factories.py`, `migrations/`,
  `tests/`, `management/commands/`.
- **Modify** `config/settings/base.py`: `LOCAL_APPS`, `MIDDLEWARE`,
  `TEMPLATES` context processors, `TENANT_BASE_DOMAIN`, `DEFAULT_TENANT_SLUG`.
- **Modify** `apps/users/models.py` (FK `organization` + helpers) y `factories.py`.
- **Modify** `apps/equipment/models.py` (FK `organization`) y `factories.py`.
- **Modify** `apps/reports/models.py` (FK `organization`), `utils.py`,
  `services/chart_export_pdf.py`, `services/component_analysis.py`.
- **Modify** `apps/core/mixins/views.py` (scoping).
- **Modify** templates de login/shell y limpieza en `users`.
- **Create** migraciones de cada app afectada + data migration MARCO.

---

## Task 1: Modelo `Organization` (app nueva)

**Files:**
- Create: `apps/organizations/__init__.py`, `apps.py`, `choices.py`,
  `constants.py`, `models.py`, `admin.py`, `factories.py`, `migrations/__init__.py`
- Modify: `config/settings/base.py` (LOCAL_APPS)
- Test: `apps/organizations/tests/test_models.py`

**Interfaces:**
- Produces: `Organization` con `kind` (`Organization.Kind`), `parent`, `slug`,
  `is_tenant`, `tenant`, `ancestors`, `descendants(include_self=True)`,
  `get_branding()`, `has_capability(key)`, `OrganizationFactory`.

- [ ] **Step 1: Test que falla** (arbol + herencia + capacidades)
- [ ] **Step 2: Correr y ver fallar** (`apps.organizations.tests.test_models`)
- [ ] **Step 3: Implementar** modelo, choices, constants, app config, admin
- [ ] **Step 4: Correr y ver pasar** + `makemigrations organizations`
- [ ] **Step 5: Commit**

## Task 2: `User.organization` y scoping helpers

**Files:**
- Modify: `apps/users/models.py`, `apps/users/factories.py`
- Create: `apps/organizations/scoping.py`
- Test: `apps/organizations/tests/test_scoping.py`, `apps/users/tests/test_models.py`

**Interfaces:**
- Consumes: `Organization` (Task 1).
- Produces: `User.organization`; `user_visible_organization_ids(user)`,
  `scope_queryset(qs, user)`.

## Task 3: Pertenencia en equipment y reports

**Files:**
- Modify: `apps/equipment/models.py` (`Fleet`, `Branch`, `Machine`),
  `apps/reports/models.py` (`Report`), factories.
- Test: `apps/equipment/tests/test_models.py`, `apps/reports/tests/test_models.py`

## Task 4: Data migration MARCO

**Files:**
- Create: migracion de datos en `apps/organizations/migrations/`
- Test: `apps/organizations/tests/test_data_migration.py`

## Task 5: Scoping en mixins base, filtros y API

**Files:**
- Modify: `apps/core/mixins/views.py`, `apps/reports/views.py`,
  `apps/equipment/views.py`, `apps/reports/filtersets.py`,
  `apps/equipment/filtersets.py`, `apps/core/autocomplete.py`,
  `apps/equipment/autocomplete.py`
- Test: `apps/core/tests/test_scoping.py`

## Task 6: Middleware, context processor y paleta

**Files:**
- Create: `apps/organizations/middleware.py`, `context_processors.py`,
  `services.py`
- Modify: `config/settings/base.py`
- Test: `apps/organizations/tests/test_services.py`, `test_middleware.py`

## Task 7: Branding en login y shell

**Files:**
- Modify: `templates/account/login.html`, `templates/includes/aside.html`,
  `templates/includes/navbar.html`, `templates/layouts/*`
- Test: `apps/organizations/tests/test_templates.py`

## Task 8: PDF + `get_parameter_color` por organizacion

**Files:**
- Modify: `apps/reports/utils.py`, `apps/reports/services/chart_export_pdf.py`,
  `apps/reports/services/component_analysis.py`
- Test: `apps/reports/tests/test_utils.py`, `apps/reports/tests/test_services.py`

## Task 9: Capacidades por `kind`

**Files:**
- Modify: `apps/organizations/constants.py`, `models.py`; templates de
  aside/dashboard/report
- Test: `apps/organizations/tests/test_capabilities.py`

## Task 10: Comando de datos de prueba

**Files:**
- Create: `apps/organizations/management/commands/seed_demo_data.py`
- Test: `apps/organizations/tests/test_seed_command.py`

## Task 11: Limpieza de codigo muerto

**Files:**
- Modify: `templates/users/account/list.html`, `templates/users/settings.html`,
  `apps/users/signals.py`, `apps/users/management/commands/add_default_users.py`,
  `apps/alerts/services/notifications.py`
- Test: `apps/users/tests/test_templates.py`

## Task 12: Verificacion final y revision

- [ ] Suite completa + `coverage report` (meta 85 %).
- [ ] `ruff check` limpio.
- [ ] Revision con `django-reviewer` del diff de la rama.
