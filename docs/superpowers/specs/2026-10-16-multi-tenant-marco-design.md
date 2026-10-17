# Diseno: plataforma multi-tenant con marca por organizacion (MARCO)

- **Fecha:** 2026-10-16
- **Estado:** Aprobado
- **Alcance:** Tenancy multi-organizacion + aislamiento de datos + branding por
  organizacion + capacidades por tipo + datos de prueba del laboratorio +
  limpieza de codigo muerto.
- **Idioma:** UI en espanol via `{% trans %}`; codigo, comentarios y docstrings
  en ingles (AGENTS.md).

## 1. Objetivo

Convertir la plataforma (hoy single-tenant) en un SaaS multi-organizacion. El
tenant inicial es **MARCO Peruana** (laboratorio de lubricantes). Dentro de un
tenant existen clientes **intermediarios** (con sus propios usuarios) y clientes
**finales** (solo ven sus resultados). Cada organizacion puede tener su propia
marca (logo + colores) y sus propias capacidades segun su tipo. A futuro debe
bastar con **crear un nuevo tenant** para vender la solucion a otro cliente que,
por ejemplo, solo gestione reportes recibidos de varios laboratorios.

## 2. Contexto actual (hallazgos)

- Modelos relevantes: `reports.Report`, `reports.LabAnalysis`,
  `reports.Laboratory`, `reports.AnalysisThreshold`, `equipment.Fleet` /
  `Branch` / `Machine` / `Component` / `ComponentType`, `users.User` /
  `users.Account`, `alerts.Alert`.
- No existe concepto de cliente/empresa/tenant. La plataforma es single-tenant.
- Existen feature flags globales (constance): `ENABLE_LABS`, `ENABLE_FLEET`,
  `ENABLE_SEND_EMAIL`, `COMPANY_LOGO`.
- Residuos de una app `customers` ya eliminada:
  - `apps/reports/utils.py::get_parameter_color(..., tenant)` importa un
    `ColorPaletteService` inexistente (`apps.core.services.color_palette_service`).
  - `apps/reports/services/chart_export_pdf.py` acepta `organization_name`, pero
    nadie lo alimenta.
  - `templates/users/account/list.html` y `templates/users/settings.html` leen
    `account.is_organization` / `filter.form.is_organization`, campos que no
    existen en el modelo.
  - Comentarios `# Migrated from customers app` en `apps/users/signals.py`.
  - Permisos muertos en `apps/users/management/commands/add_default_users.py`
    (`orderresult`, `medicaltestresult`) de apps inexistentes.
- Marca hardcodeada: "LUBEAI" en `templates/includes/aside.html`, `[LubeAI]` en
  el asunto de `apps/alerts/services/notifications.py`, `logo.png`.

## 3. Decisiones acordadas

| Tema | Decision |
|------|----------|
| Frontera de aislamiento | El **tenant** (organizacion raiz) es la frontera dura; nunca se ven datos entre tenants. |
| Jerarquia | Arbol con auto-referencia: Tenant -> Intermediario -> Final. |
| Gestion | MARCO gestiona su tenant completo; el **Intermediario** gestiona su sub-arbol (finales, equipos, usuarios); el **Final** es solo lectura. |
| Tipo vs flag | Las capacidades son **por tenant** (segun `kind`); los flags globales quedan solo para cosas de instancia (correo) y como override maestro durante la transicion. |
| Resolucion de tenant | **Subdominio** por host, con **slug por ruta/sesion** como respaldo para desarrollo. |
| Branding | Slots fijos (primary + colores de charts) con **herencia** padre -> hijo; se aplica a **login** y shell. |
| Migracion | FKs de organizacion **nullable**; data migration crea el root MARCO y asigna la data existente. Sin renombrar/borrar modelos. |

## 4. Modelo de datos

### 4.1 `Organization` (nueva app `apps/organizations`)

- `name`, `slug` (unico), `code` (unico, opcional), `description`.
- `parent` (FK a si mismo, `null` => es un tenant).
- `kind`: `PLATFORM` | `LAB` | `INTERMEDIARY` | `FINAL`.
- `is_active`.
- Branding: `logo` (imagen), `primary_color` y colores de charts
  (`chart_primary`, `chart_success`, `chart_warning`, `chart_danger`,
  `chart_info`, `chart_dark`).
- `capabilities` (JSON) con overrides sobre las capacidades por defecto del `kind`.
- Contacto/direccion reutilizando `core.BaseContact` / `core.BaseAddress`.

Metodos: `is_tenant`, `tenant` (raiz), `ancestors`, `descendants(include_self)`,
`get_branding()` (con herencia), `has_capability(key)`.

### 4.2 Pertenencia

- `equipment.Branch`, `equipment.Machine`, `equipment.Fleet`: FK `organization`
  (nullable).
- `reports.Report`: FK `organization` (nullable, heredado de la maquina).
- `users.User`: FK `organization` (nullable) para el scoping.

## 5. Resolucion de tenant y contexto

- `apps/organizations/middleware.py::TenantMiddleware` (tras
  `AuthenticationMiddleware`): resuelve `request.organization` (la del usuario
  autenticado) y `request.tenant` (por host/subdominio, con respaldo a
  `DEFAULT_TENANT_SLUG` en desarrollo).
- `apps/organizations/context_processors.py::branding`: expone `branding`,
  `current_organization` y `current_tenant` a las plantillas.
- `apps/organizations/services.py::ColorPaletteService.get_palette(org)`:
  resuelve colores con herencia y defaults.

## 6. Aislamiento (scoping)

- `apps/organizations/scoping.py`:
  - `user_visible_organization_ids(user)` -> `None` para admins de plataforma
    (sin restriccion) o el conjunto de ids del sub-arbol del usuario.
  - `scope_queryset(queryset, user, field="organization")` -> filtra si el
    modelo tiene el campo.
- Se aplica en los mixins base (`apps/core/mixins/views.py`) para `BaseListView`,
  `BaseDetailView`, `BaseUpdateView` y `BaseDeleteView`, y en los endpoints de
  API/autocompletado y en los `FilterSet` (querysets de `ModelChoiceFilter`).

## 7. Capacidades por tipo

- Mapa `kind -> capacidades por defecto` en `apps/organizations/constants.py`.
- `ENABLE_LABS` / `ENABLE_FLEET` dejan de ser la unica fuente: se consultan via
  `organization.has_capability("labs" | "fleet")`, con el flag global como
  override maestro (si el flag global esta apagado, se oculta para todos).

## 8. Branding

- Variables CSS inyectadas desde el context processor; el aside/navbar/login
  usan `{{ branding.primary_color }}` y `{{ branding.logo }}`.
- El footer del PDF de analisis de componentes usa el nombre de la organizacion.
- Se elimina la marca hardcodeada "LUBEAI" / `[LubeAI]`.

## 9. Migracion y no ruptura

- Migraciones con FKs nullable.
- Data migration idempotente: crea `Organization(slug="marco", kind=LAB,
  parent=None)` y asigna a MARCO toda la data existente
  (`Branch`, `Machine`, `Fleet`, `Report`) y los usuarios existentes.
- Sin renombrar ni borrar modelos.

## 10. Datos de prueba

- Management command idempotente `seed_demo_data` (nombre final en el plan) que
  crea: tenant MARCO, un intermediario, clientes finales, usuarios por rol,
  equipos (branches/machines/components), umbrales y **muchos informes
  historicos por componente** (series mensuales a lo largo de varios anos) para
  el analisis de componentes. Reutiliza las factories existentes.

## 11. Limpieza de codigo muerto

- `get_parameter_color` + `ColorPaletteService` (se reimplementan bien).
- `organization_name` del PDF (se alimenta con la organizacion del reporte).
- `is_organization` en plantillas de `users` (contra campos inexistentes).
- Comentarios `# Migrated from customers app`.
- Marca hardcodeada.
- Permisos muertos en `add_default_users`.

## 12. Pruebas (meta 85 %)

- `organizations`: modelo (arbol, herencia de branding, capacidades), scoping,
  middleware, context processor, servicios.
- `users` / `equipment` / `reports`: scoping por organizacion en listados,
  detalle, export y API; no fuga entre tenants.
- Branding aplicado en login/shell; PDF con nombre de organizacion.
- Seeds: crea la jerarquia y series historicas.
- Comando: `docker compose exec django coverage run manage.py test
  --settings=config.settings.testing`.

## 13. Fuera de alcance

- Facturacion / planes por tenant.
- Limites de uso por tenant.
- Dominios propios por cliente (solo subdominio de la plataforma).
