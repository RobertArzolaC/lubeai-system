# Marco multi-tenant por esquemas de PostgreSQL (opción B) — Plan de implementación

> **Para el agente implementador:** SUB-SKILL REQUERIDO: usa `superpowers:subagent-driven-development` (recomendado, tarea por tarea con revisor) o `superpowers:executing-plans` (ejecución nativa). Los pasos usan casillas (`- [ ]`).

**Goal:** Convertir la plataforma en un SaaS con **aislamiento duro por esquema PostgreSQL**: cada cliente de la plataforma (laboratorio, intermediario o cliente final) obtiene su propio esquema, su propio subdominio y sus propios usuarios; dentro del esquema del laboratorio se conserva el árbol de organizaciones por subárbol ya construido.

**Architecture:** `django-tenants` con `django_tenants.postgresql_backend`. El registro de tenants (`Tenant` con `TenantMixin`, `Domain` con `DomainMixin`) vive en el esquema `public` (SHARED). Todo lo demás —usuarios, autenticación, reportes, equipos, alertas y el árbol de organizaciones— vive en el esquema de cada tenant (TENANT). La vista consolidada del laboratorio sigue siendo **una sola consulta**, porque todo su árbol está dentro de su propio esquema. El panel de la plataforma es un tenant de operaciones (`ops`) que, gracias a que `public` está siempre en el `search_path`, ve el registro de tenants.

**Tech Stack:** Django 6.0.8, PostgreSQL 16, `django-tenants`, `tenant-schemas-celery`, Celery 5.6 + django-celery-beat, django-allauth 65, django-filter 26, django-constance 4.3.5, django-cities-light, Tailwind (TailAdmin), tests con `unittest` (`TenantTestCase`/`FastTenantTestCase`) y `factory_boy`.

**Spec:** decisiones acordadas con el usuario:
- **Frontera de aislamiento:** el **cliente de la plataforma** (raíz) es la frontera dura, materializada como **esquema PostgreSQL**.
- **Jerarquía:** dentro del esquema del cliente (si es laboratorio) se conserva el árbol `Organization` con `parent`: intermediario → final.
- **Usuarios por tenant (opción B):** `auth`, `users`, `admin`, `sessions`, `sites` viven en el esquema del tenant. No hay usuarios globales.
- **Un cliente sin hijos** (un intermediario o final que contrata directo) es un **tenant propio**, no una organización suelta.
- **Administración de la plataforma:** tenant `ops` (el esquema `public` no puede tener admin).
- **Métricas y costos:** consumo medible por esquema; un droplet puede alojar N esquemas y un cliente grande puede graduarse a su propio droplet cambiando solo su `DATABASE_URL`.
- **Sin ruptura:** los FKs actuales se conservan; la data existente se migra a un esquema nuevo mediante migración de datos idempotente.
- **Descriptor de trabajo:** rama base `feat/multi-tenant-branding` (55 commits) integrada a `main` antes de empezar.

---

## Global Constraints

- Código, comentarios y docstrings en **inglés** (AGENTS.md). Este plan y la comunicación van en español.
- Tipado y docstrings **PEP 257** en cada función/clase que se cree o modifique; conservar comentarios existentes.
- **PostgreSQL obligatorio** en todos los entornos, incluido desarrollo y tests. SQLite queda prohibido: rompe `django_tenants.postgresql_backend`.
- **Regla dura de `SHARED_APPS`:** ninguna app de SHARED puede tener FK hacia un modelo de TENANT. Consecuencia directa: `organizations`, `users`, `reports`, `equipment`, `alerts` y cualquier modelo con `created_by`/`updated_by` van en TENANT.
- **Regla dura de aislamiento:** ninguna consulta puede cruzar esquemas. El `search_path` de un tenant es siempre `<tenant>, public`.
- El módulo de tenant model (`apps/tenancy`) va **obligatoriamente** en `SHARED_APPS`.
- Ningún dato de negocio en el esquema `public`.
- Tests: `unittest` + factories; casos de tenant con `TenantTestCase`/`FastTenantTestCase`. Comando oficial: `docker compose exec web coverage run manage.py test --settings=config.settings.testing`.
- Cobertura mínima **85 %**.
- Lint: `uv run ruff check <paths>`.
- La rama `feat/multi-tenant-branding` **no se elimina** hasta que `main` esté verde tras la integración.
- UI en español vía `{% trans %}`; catálogos `locale/es` y `locale/en` actualizados.

## Review Focus

1. **Host sin tenant y sin `SHOW_PUBLIC_IF_NO_TENANT_FOUND`:** una petición a un subdominio inexistente (`noexiste.midominio.com`) debe responder **404**, nunca caer al tenant por defecto. El bug actual (`DEFAULT_TENANT_SLUG="marco"`) hace que cualquier host desconocido aterrice en MARCO.
2. **Fuga cross-tenant por id:** un usuario autenticado en `acme` pidiendo `/reports/<pk_de_marco>/`, `/machines/<pk>/` o `/organizations/<pk>/` debe recibir **404**, aunque el `pk` exista en otro esquema.
3. **Celery sin contexto de esquema:** una tarea de alertas disparada por beat debe ejecutarse explícitamente por tenant. Si corre sin `search_path` fijado, escribiría alertas de un cliente en el esquema de otro (o en `public`). El comportamiento esperado es iterar tenants de forma explícita, nunca escribir en el esquema `public`.
4. **FK prohibida SHARED → TENANT:** si un modelo de SHARED (p. ej. `Tenant.created_by`) apunta a `users.User`, `migrate_schemas --shared` debe **fallar de forma visible** en desarrollo. El comportamiento correcto es que la FK no exista; el bug silencioso es que se cree y falle en el primer `migrate` de un tenant.
5. **Esquema nuevo sin `sites.Site`:** tras `provision_tenant`, `allauth` debe funcionar sin `Site.DoesNotExist`. El comportamiento esperado es que la provisión cree el `Site` del esquema; el bug es un 500 en el primer login del tenant nuevo.

---

## File Structure

- **Create** `apps/tenancy/` (SHARED): `models.py` (`Tenant`, `Domain`), `apps.py`, `admin.py`, `services.py` (provisión y consumo), `management/commands/provision_tenant.py`, `management/commands/seed_demo_data.py` (movido desde `organizations`), `migrations/0001_initial.py`, `tests/`.
- **Modify** `config/settings/base.py` — `SHARED_APPS`/`TENANT_APPS`, `INSTALLED_APPS`, `DATABASE_ROUTERS`, backend de BD, `TENANT_MODEL`, `TENANT_DOMAIN_MODEL`, `PUBLIC_SCHEMA_URLCONF`, `TENANT_LIMIT_SET_CALLS`, `ALLOWED_HOSTS`.
- **Modify** `config/settings/development.py` y `config/settings/testing.py` — forzar PostgreSQL; retirar el fallback SQLite.
- **Create** `config/urls_public.py` — `PUBLIC_SCHEMA_URLCONF` (landing pública sin sesión ni admin).
- **Modify** `apps/organizations/models.py` — `Organization` pasa a TENANT: conserva `parent`, `kind`, branding, `capabilities`; pierde la unicidad global de `slug` (queda único por esquema) y deja de tener raíces.
- **Modify** `apps/organizations/middleware.py` — **se elimina**; lo reemplaza `TenantMainMiddleware` de django-tenants.
- **Modify** `apps/organizations/context_processors.py` — resuelve branding desde `request.tenant` (SHARED) y `request.organization` (TENANT).
- **Modify** `apps/organizations/scoping.py` — se conserva íntegro para el subárbol intra-tenant; se retiran de aquí las decisiones de tenant.
- **Modify** `apps/users/models.py`, `apps/users/migrations/` — usuarios por esquema (la app pasa a TENANT; sin cambios de campos).
- **Modify** `apps/users/management/commands/add_default_users.py` — pasa a comando de tenant (`BaseTenantCommand`).
- **Modify** `config/celery.py` + `apps/alerts/tasks.py` — integración `tenant-schemas-celery`.
- **Modify** `docker-compose.yml` / `docker-compose.override.yml` — Postgres obligatorio; comando de arranque con `migrate_schemas`.
- **Modify** `pyproject.toml` — añadir `django-tenants` y `tenant-schemas-celery`.
- **Sin cambios (revisado):** `apps/organizations/scoping.py` (lógica interna), `apps/reports/**`, `apps/equipment/**`, `apps/alerts/models.py`, `apps/dashboard/**` y las plantillas, salvo los ajustes de resolución de tenant/branding.

---

## Task 0: Preservar la base actual (Fase 0, previa a todo)

**Files:**
- Sin cambios de código.

**Interfaces:**
- Produces: `main` con los 55 commits integrados y verde; rama respaldada en `origin`.

- [ ] **Step 1: Respaldar la rama en `origin`**

```bash
git push -u origin feat/multi-tenant-branding
```
Expected: la rama existe en `origin`. (Hoy solo está en local: si se pierde la máquina, se pierde todo.)

- [ ] **Step 2: Confirmar que la integración es fast-forward**

```bash
git merge-base --is-ancestor main feat/multi-tenant-branding && echo "fast-forward"
git rev-list --count main..feat/multi-tenant-branding
```
Expected: `fast-forward` y `55`.

- [ ] **Step 3: Integrar a `main`**

```bash
git checkout main
git merge --ff-only feat/multi-tenant-branding
git push origin main
```

- [ ] **Step 4: Establecer la línea base verde (basura cero antes de empezar)**

```bash
docker compose up -d --build
docker compose exec web coverage run manage.py test --settings=config.settings.testing
docker compose exec web coverage report --sort=cover
```
Expected: 0 fallos. **Anota el porcentaje de cobertura actual y guárdalo**: es el listón que no se puede bajar.

- [ ] **Step 5: Commit (si hubo cambios de configuración local)**

```bash
git status --short
# commitear solo si el merge dejó cambios pendientes legítimos
```

---

## Task 1: Esqueleto de esquemas (`apps/tenancy` + settings)

**Files:**
- Create: `apps/tenancy/__init__.py`, `apps/tenancy/apps.py`, `apps/tenancy/models.py`, `apps/tenancy/migrations/__init__.py`, `apps/tenancy/tests/__init__.py`
- Modify: `config/settings/base.py`, `config/settings/development.py`, `config/settings/testing.py`, `pyproject.toml`
- Test: `apps/tenancy/tests/test_models.py`

**Interfaces:**
- Produces: `apps.tenancy.models.Tenant` (hereda `TenantMixin`; campos `name`, `slug`, `kind`, `is_active`, branding y `capabilities`), `apps.tenancy.models.Domain` (hereda `DomainMixin`), `settings.SHARED_APPS`, `settings.TENANT_APPS`, `settings.TENANT_MODEL = "tenancy.Tenant"`, `settings.TENANT_DOMAIN_MODEL = "tenancy.Domain"`.

- [ ] **Step 1: Añadir dependencias**

En `pyproject.toml`, en `dependencies`, añade `django-tenants` y `tenant-schemas-celery`; y mueve `psycopg2-binary` del grupo `production` a `dependencies` (PostgreSQL pasa a ser obligatorio en todos los entornos).

```bash
uv sync
```

- [ ] **Step 2: Escribe el test que falla**

```python
# apps/tenancy/tests/test_models.py
"""Tests for the shared tenancy registry."""

from django.test import TestCase

from apps.tenancy import models


class TenantModelTests(TestCase):
    """``Tenant`` is the hard isolation boundary of the platform."""

    def test_tenant_creation_creates_schema(self) -> None:
        """Creating a tenant creates its PostgreSQL schema."""
        tenant = models.Tenant.objects.create(name="ACME", slug="acme")
        self.assertEqual(tenant.schema_name, "acme")
        self.assertTrue(tenant.is_active)
```

- [ ] **Step 3: Ejecuta el test y verifica que falla**

Run: `docker compose exec web python manage.py test apps.tenancy.tests.test_models`
Expected: FAIL — `ModuleNotFoundError: apps.tenancy`.

- [ ] **Step 4: Implementa `apps/tenancy`**

`apps/tenancy/models.py`:

```python
class Tenant(TenantMixin):
    """A platform client; the hard isolation boundary (one schema each)."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=20, choices=choices.OrganizationKind.choices)
    is_active = models.BooleanField(default=True)
    # branding/capabilities: mismos slots que hoy en Organization.
    auto_create_schema = True


class Domain(DomainMixin):
    """A host name served by a tenant."""


class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):  # TenantAdminMixin de django_tenants
    list_display = ("name", "slug", "kind", "is_active")
```

**Decisión cerrada:** `Tenant` **no** incluye `created_by`/`updated_by`. Un FK de SHARED hacia `users.User` (TENANT) es inválido y haría fallar `migrate_schemas --shared` (ver Review Focus 4).

- [ ] **Step 5: Configura los settings**

En `config/settings/base.py`:

```python
SHARED_APPS = [
    "django_tenants",
    "apps.tenancy",
    "django.contrib.contenttypes",
    "cities_light",
    "constance",
    "constance.backends.database",
]

TENANT_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "allauth", "allauth.account",
    "easy_audit",
    "apps.core", "apps.authentication", "apps.users", "apps.theme",
    "apps.organizations", "apps.equipment", "apps.reports",
    "apps.alerts", "apps.dashboard",
]

INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]

DATABASES = {"default": db_url(config("DATABASE_URL"))}
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)
TENANT_MODEL = "tenancy.Tenant"
TENANT_DOMAIN_MODEL = "tenancy.Domain"
PUBLIC_SCHEMA_URLCONF = "config.urls_public"
TENANT_LIMIT_SET_CALLS = True
ALLOWED_HOSTS = [".midominio.com", "localhost"]  # ajustar al dominio real
```

Retira `apps.organizations.middleware.TenantMiddleware` y las settings `TENANT_BASE_DOMAIN` / `DEFAULT_TENANT_SLUG` (las reemplaza `Domain`).

- [ ] **Step 6: Crea la base, migra SHARED y verifica**

```bash
docker compose exec web python manage.py migrate_schemas --shared
docker compose exec web python manage.py test apps.tenancy.tests.test_models
```
Expected: PASS (1 test). El esquema `public` contiene `tenancy_tenant` y `tenancy_domain`.

- [ ] **Step 7: Commit**

```bash
git add apps/tenancy config/settings pyproject.toml uv.lock
git commit -m "feat(tenancy): add schema-per-tenant skeleton with django-tenants"
```

---

## Task 2: `Organization` pasa a TENANT y pierde su rol de raíz

**Files:**
- Modify: `apps/organizations/models.py`, `apps/organizations/migrations/`
- Delete: `apps/organizations/middleware.py`
- Test: `apps/organizations/tests/test_models.py`, `apps/organizations/tests/test_scoping.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Tenant`.
- Produces: `apps.organizations.models.Organization` con `parent`, `kind`, `branding`, `capabilities` y `slug` **único por esquema** (no global); sin raíces (`parent` requerido salvo la fila raíz del tenant).

- [ ] **Step 1: Escribe los tests que fallan**

```python
    def test_slug_unique_within_schema(self) -> None:
        """Slugs are unique inside a tenant's schema, not globally."""
        factories.OrganizationFactory(slug="planta-norte")
        with self.assertRaises(IntegrityError):
            factories.OrganizationFactory(slug="planta-norte")
```

```python
    def test_subtree_scoping_still_isolates_children(self) -> None:
        """A final client cannot see a sibling subtree."""
        # (conservar y adaptar el test existente de scoping)
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `docker compose exec web python manage.py test apps.organizations.tests.test_models`
Expected: FAIL (el esquema aún no existe / `slug` sigue siendo único global).

- [ ] **Step 3: Adapta el modelo y elimina el middleware propio**

- Quita `unique=True` de `Organization.slug` y añade `UniqueConstraint(fields=["slug"])` (único por esquema por construcción).
- Elimina `apps/organizations/middleware.py`.
- Añade la migración que crea el árbol dentro del esquema del tenant.

- [ ] **Step 4: Migra y verifica**

```bash
docker compose exec web python manage.py migrate_schemas
docker compose exec web python manage.py test apps.organizations
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/organizations
git commit -m "refactor(organizations): move the client tree into the tenant schema"
```

---

## Task 3: Usuarios, autenticación y landing pública

**Files:**
- Create: `config/urls_public.py`
- Modify: `apps/organizations/context_processors.py`, `apps/users/management/commands/add_default_users.py`
- Test: `apps/users/tests/test_models.py`, `apps/organizations/tests/test_context_processors.py`

**Interfaces:**
- Consumes: `request.tenant` (lo pone `TenantMainMiddleware`).
- Produces: branding resuelto por request (`branding`, `current_organization`, `current_tenant`, `capabilities`, `show_labs`, `show_fleet`), y una landing pública en `config.urls_public`.

- [ ] **Step 1: Escribe los tests que fallan**

```python
class BrandingTenantTests(TenantTestCase):
    """Branding resolves from the request tenant inside the tenant schema."""

    def test_branding_falls_back_to_tenant_defaults(self) -> None:
        """With no organization in context the tenant brand is used."""
        request = self.client.get("/").wsgi_request  # ajustar al helper usado
        context = context_processors.branding(request)
        self.assertEqual(context["current_tenant"], self.tenant)
```

- [ ] **Step 2: Ejecuta y verifica que fallan**

Run: `docker compose exec web python manage.py test apps.organizations.tests.test_context_processors`
Expected: FAIL.

- [ ] **Step 3: Implementa**

- `config/urls_public.py`: landing sin sesión ni admin (lista/redirección a subdominios, o página informativa).
- `context_processors.branding`: resolver `request.tenant` desde el middleware de django-tenants; degradar a los defaults cuando no haya tenant.
- `add_default_users`: heredar de `django_tenants.management.commands.BaseTenantCommand` para que corra por esquema.
- Configurar `root urlconf` para que el esquema `public` use `config.urls_public`.

- [ ] **Step 4: Verifica**

```bash
docker compose exec web python manage.py test apps.users apps.organizations
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/urls_public.py apps/users apps/organizations/context_processors.py
git commit -m "feat(tenancy): per-tenant users, branding from tenant and public landing"
```

---

## Task 4: Migración de datos y provisión de tenants

**Files:**
- Create: `apps/tenancy/management/commands/provision_tenant.py`, `apps/tenancy/management/commands/seed_demo_data.py`
- Delete: `apps/organizations/management/commands/seed_demo_data.py`, `apps/organizations/migrations/0002_seed_marco_tenant.py`
- Create: `apps/tenancy/migrations/0002_seed_marco_tenant.py`
- Test: `apps/tenancy/tests/test_provision_command.py`, `apps/tenancy/tests/test_seed_command.py`

**Interfaces:**
- Consumes: `Tenant`, `Domain`, `Organization`, `provision_tenant`.
- Produces: `provision_tenant(slug, name, kind, admin_email, default_password)` idempotente, que crea el tenant, su dominio, su esquema migrado, su `Site`, su organización raíz, su admin y sus permisos.

- [ ] **Step 1: Escribe los tests que fallan**

```python
class ProvisionTenantTests(TenantTestCase):
    """Provisioning a tenant leaves it immediately usable."""

    def test_provision_creates_schema_site_and_admin(self) -> None:
        """A new tenant has a schema, a Site and a working admin user."""
        tenant = services.provision_tenant(
            slug="acme", name="ACME", kind="intermediary",
            admin_email="admin@acme.pe", default_password="Demo12345!",
        )
        self.assertEqual(tenant.schema_name, "acme")
        self.assertEqual(Site.objects.count(), 1)
        self.assertTrue(User.objects.filter(email="admin@acme.pe").exists())
```

- [ ] **Step 2: Ejecuta y verifica que falla**

Run: `docker compose exec web python manage.py test apps.tenancy.tests.test_provision_command`
Expected: FAIL — `AttributeError: module 'services' has no attribute 'provision_tenant'`.

- [ ] **Step 3: Implementa `provision_tenant` y mueve el seeding**

- `provision_tenant`: crea `Tenant` (dispara `auto_create_schema`) → migra el esquema → crea `Domain` → dentro del esquema: `Site`, organización raíz, admin con permisos, capacidades y tipos de componente por defecto.
- `seed_demo_data`: se mueve a `apps/tenancy` y pasa a crear **primero** el tenant y luego la jerarquía dentro del esquema. Conserva `--months` y `--seed`; se le añaden `--machines` y `--components` para ampliar el histórico (ver Task 8).
- Elimina `apps/organizations/migrations/0002_seed_marco_tenant.py` (la reemplaza la migración de `Tenant`).

- [ ] **Step 4: Verifica**

```bash
docker compose exec web python manage.py provision_tenant --slug marco --name "MARCO Peruana" --kind lab --admin-email admin@marco.pe
docker compose exec web python manage.py seed_demo_data --schema marco
```
Expected: reporta organizaciones, máquinas e informes creados, sin duplicar al reejecutar.

- [ ] **Step 5: Commit**

```bash
git add apps/tenancy apps/organizations
git commit -m "feat(tenancy): tenant provisioning and per-tenant demo seeding"
```

---

## Task 5: Celery por tenant

**Files:**
- Modify: `config/celery.py`, `config/settings/base.py`, `apps/alerts/tasks.py`
- Test: `apps/alerts/tests/test_tasks.py`

**Interfaces:**
- Consumes: `tenant-schemas-celery`.
- Produces: tareas de alertas ejecutadas explícitamente por esquema.

- [ ] **Step 1: Escribe el test que falla**

```python
    def test_alert_task_runs_per_tenant(self) -> None:
        """The notification task iterates tenants instead of using public."""
        # Verifica que la tarea fija el esquema del tenant antes de escribir.
```

- [ ] **Step 2: Ejecuta y verifica que falla**

Run: `docker compose exec web python manage.py test apps.alerts.tests.test_tasks`
Expected: FAIL.

- [ ] **Step 3: Implementa**

- Registra `tenant_schemas_celery` en Celery (`config/celery.py`).
- `apps/alerts/tasks.py`: la tarea de notificaciones recorre `Tenant.objects.filter(is_active=True)` y ejecuta por esquema de forma explícita; nunca escribe en `public`.

- [ ] **Step 4: Verifica**

```bash
docker compose exec web python manage.py test apps.alerts
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/celery.py config/settings/base.py apps/alerts
git commit -m "feat(alerts): run notification tasks per tenant schema"
```

---

## Task 6: Migrar la suite de tests y probar las fugas cross-tenant

**Files:**
- Modify: todo `apps/*/tests/**` que hoy use `django.test.TestCase` y toque modelos de TENANT.
- Create: `apps/tenancy/tests/test_isolation.py`

**Interfaces:**
- Consumes: `TenantTestCase`, `FastTenantTestCase`, `TenantClient`.
- Produces: suite completa verde bajo esquemas.

- [ ] **Step 1: Escribe los tests de aislamiento que fallan**

```python
class CrossTenantIsolationTests(TenantTestCase):
    """No data crosses the schema boundary."""

    def test_other_tenant_object_is_not_reachable_by_id(self) -> None:
        """An object that exists only in another tenant returns 404."""
        other = models.Tenant.objects.create(name="Other", slug="other")
        # crear un reporte en `other` y pedirlo desde este tenant → 404
```

- [ ] **Step 2: Ejecuta y verifica que falla**

Run: `docker compose exec web python manage.py test apps.tenancy.tests.test_isolation`
Expected: FAIL (los tests aún corren en un solo esquema).

- [ ] **Step 3: Migra la suite**

- Cambia `django.test.TestCase` → `TenantTestCase` (o `FastTenantTestCase`) en los módulos que tocan modelos de TENANT.
- Sustituye `self.client` por `TenantClient(self.tenant)`.
- Ajusta los factories: `OrganizationFactory` deja de crear raíces; `TenantFactory` las crea.
- Revisa `assertNumQueries` del dashboard: debe **seguir siendo 1 consulta** para el agregado consolidado del laboratorio (regresión crítica).

- [ ] **Step 4: Verifica**

```bash
docker compose exec web coverage run manage.py test --settings=config.settings.testing
docker compose exec web coverage report --sort=cover
```
Expected: 0 fallos y cobertura ≥ el listón anotado en Task 0, Step 4.

- [ ] **Step 5: Commit**

```bash
git add apps
git commit -m "test(tenancy): migrate suite to tenant test cases and cover cross-tenant leaks"
```

---

## Task 7: Tenant de operaciones, provisión de clientes y métricas de consumo

**Files:**
- Create: `apps/tenancy/views.py`, `apps/tenancy/urls.py`, `apps/tenancy/forms.py`, `apps/tenancy/filtersets.py`, `apps/tenancy/services.py` (ampliación)
- Create: `templates/tenancy/tenant/{list,detail,form}.html`
- Modify: `templates/includes/aside.html`, `config/urls.py`, `apps/tenancy/admin.py`
- Test: `apps/tenancy/tests/test_views.py`, `apps/tenancy/tests/test_consumption.py`

**Interfaces:**
- Consumes: `Tenant`, `Domain`, `provision_tenant`, `scoping` (reutilizado para acotar por tenant en el registro SHARED).
- Produces: `TenantService.consumption(tenant) -> dict` con `{rows, bytes, reports, machines, users}`; CRUD de tenants desde el tenant `ops`.

- [ ] **Step 1: Escribe los tests que fallan**

```python
class ConsumptionServiceTests(TenantTestCase):
    """Usage per tenant is measurable for billing."""

    def test_consumption_reports_bytes_and_rows(self) -> None:
        """Consumption returns a positive byte count for a seeded tenant."""
        data = services.TenantService.consumption(self.tenant)
        self.assertGreater(data["bytes"], 0)
        self.assertIn("reports", data)
```

- [ ] **Step 2: Ejecuta y verifica que falla**

Run: `docker compose exec web python manage.py test apps.tenancy.tests.test_consumption`
Expected: FAIL.

- [ ] **Step 3: Implementa**

- `TenantService.consumption`: `pg_total_relation_size` sumado sobre las tablas del esquema, más conteos por tabla.
- CRUD de tenants (listar, crear, suspender, branding y capacidades) reutilizando los patrones de `apps/organizations` (mixins, `django-filter`, `widget_tweaks`).
- El menú "Clientes" del aside apunta al CRUD de tenants cuando se está en el tenant `ops`.
- `docker compose`: un servicio por droplet reutilizando la misma imagen y distinta `DATABASE_URL`; documentar en `docs/` el alta de un droplet y la configuración de DNS/subdominio.

- [ ] **Step 4: Verifica**

```bash
docker compose exec web python manage.py test apps.tenancy
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/tenancy templates/tenancy templates/includes/aside.html config/urls.py
git commit -m "feat(tenancy): ops tenant console and per-tenant consumption metrics"
```

---

## Task 8: Branding real de MARCO y datos de prueba ampliados

**Files:**
- Modify: `apps/tenancy/management/commands/*`, `apps/tenancy/models.py`
- Test: `apps/tenancy/tests/test_seed_command.py`

**Interfaces:**
- Consumes: `seed_demo_data --schema marco --months N`.
- Produces: tenant MARCO con logo y paleta reales, y un histórico largo por componente.

- [ ] **Step 1: Escribe el test que falla**

```python
    def test_seed_creates_long_component_history(self) -> None:
        """Each seeded component has a long monthly report history."""
        call_command("seed_demo_data", schema="marco", months=36)
        report = Report.objects.order_by("component_id", "sample_date").first()
        history = Report.objects.filter(component_id=report.component_id).count()
        self.assertGreaterEqual(history, 36)
```

- [ ] **Step 2: Ejecuta y verifica que falla**

Run: `docker compose exec web python manage.py test apps.tenancy.tests.test_seed_command`
Expected: FAIL con `months=36` (el histórico actual es de 18 y por menos componentes).

- [ ] **Step 3: Investiga e implementa la marca**

- Obtén de `https://www.marco.com.pe/` y su LinkedIn el logo y los colores corporativos reales.
- Carga `logo`, `primary_color` y los slots `chart_*` en el tenant MARCO.
- Amplía el seeding: `--months` por defecto 36, más máquinas y más componentes por cliente final, manteniendo la idempotencia (`lab_number` estable) y la evolución de condición por componente.

- [ ] **Step 4: Verifica**

```bash
docker compose exec web python manage.py test apps.tenancy.tests.test_seed_command
docker compose exec web python manage.py seed_demo_data --schema marco --months 36
```
Expected: PASS y el análisis de componentes muestra series largas.

- [ ] **Step 5: Commit**

```bash
git add apps/tenancy
git commit -m "feat(tenancy): MARCO branding and richer lab demo history"
```

---

## Task 9: Pendientes, limpieza, cobertura y revisión

**Files:**
- Modify: `docs/Pendientes.md`, `templates/dashboard/**`, `templates/alerts/alert/list.html`, `apps/dashboard/**`, `apps/alerts/**`
- Modify: `locale/es/LC_MESSAGES/django.po` (+`.mo`), `locale/en/LC_MESSAGES/django.po`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: pendientes cerrados, código muerto eliminado, catálogos al día.

- [ ] **Step 1: Cierra los pendientes de `docs/Pendientes.md`**

- Búsqueda en los filtros del dashboard.
- Modal para actualizar **solo** el estado de la alerta.
- Verificar el filtro y la columna por organización en "Informes" y "Umbrales" (ya entró en el commit `946e08f`; si está completo, retirarlo del documento y, si no, terminarlo).

- [ ] **Step 2: Limpieza de código sin uso**

Verifica con `ruff` y `git diff` y elimina:
- El `TenantMiddleware` propio y las settings `TENANT_BASE_DOMAIN` / `DEFAULT_TENANT_SLUG` si sobrevive alguna referencia.
- `apps/organizations/middleware.py` y el `seed_demo_data` antiguo si quedaran residuos.
- Residuos de la app `customers` que aún existan en `main` (`is_organization`, `# Migrated from customers app`, marca hardcodeada `LUBEAI`).
- Ramas muertas del JS del dashboard dejadas por los feature flags.

- [ ] **Step 3: Actualiza catálogos i18n**

```bash
docker compose exec web python manage.py makemessages -l es -l en --ignore ".venv/*"
docker compose exec web python manage.py compilemessages --ignore ".venv/*"
```

- [ ] **Step 4: Suite completa con cobertura**

```bash
docker compose exec web coverage run manage.py test --settings=config.settings.testing
docker compose exec web coverage report --sort=cover
```
Expected: 0 fallos, cobertura ≥ 85 % y ≥ el listón de Task 0.

- [ ] **Step 5: Lint**

```bash
docker compose exec web ruff check apps config
```
Expected: `All checks passed!`.

- [ ] **Step 6: Revisión con `django-reviewer`**

Invoca el skill `django-reviewer` sobre todo el diff del plan. Reporta hallazgos y aplica solo refinamientos que no cambien comportamiento. Vuelve a ejecutar Steps 4-5 tras cualquier edición.

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: close pending tasks, clean dead code and refresh catalogs"
```

---

## Criterios de aceptación

- [ ] `main` contiene los 55 commits de `feat/multi-tenant-branding` y la rama está respaldada en `origin`.
- [ ] PostgreSQL es obligatorio; no queda ningún camino que arranque con SQLite.
- [ ] `migrate_schemas --shared` crea únicamente apps SHARED en `public`.
- [ ] Un host sin tenant responde **404** (no cae a MARCO).
- [ ] Un usuario de un tenant no puede alcanzar por `pk` un objeto de otro tenant (404).
- [ ] `seed_demo_data` es idempotente y produce ≥ 36 meses de histórico por componente.
- [ ] El dashboard consolidado de MARCO agrega en **una sola consulta** (sin N+1 por esquema).
- [ ] Las tareas de Celery escriben siempre en el esquema correcto.
- [ ] MARCO tiene logo y paleta reales; el branding se aplica en login y shell.
- [ ] `provision_tenant` deja un cliente nuevo operativo (esquema, dominio, `Site`, admin, permisos).
- [ ] El tenant `ops` permite listar, crear y suspender clientes, y ver su consumo.
- [ ] Suite completa verde, cobertura ≥ 85 %, `ruff` limpio y `django-reviewer` aplicado.

## Riesgos y costos asumidos

1. **PostgreSQL obligatorio**: el desarrollo local sin Docker deja de funcionar con SQLite.
2. **Suite de tests**: es el costo más alto y el más subestimado; `FastTenantTestCase` es necesario para que no se vuelva lenta.
3. **Sin admin en el esquema público**: toda la operación de plataforma pasa por el tenant `ops` o por `manage.py tenant_command`.
4. **Celery**: `tenant-schemas-celery` es integración real, no configuración.
5. **Duplicación de datos de referencia**: `cities_light` queda en SHARED a propósito; si se moviera a TENANT, se repetirían decenas de miles de filas por cliente.
6. **Esquema `public` sin datos de negocio**: cualquier consulta de negocio ejecutada fuera de un contexto de tenant debe fallar de forma visible, no devolver vacío silenciosamente.
