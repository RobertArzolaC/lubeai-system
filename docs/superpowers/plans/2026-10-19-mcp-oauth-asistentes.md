# MCP OAuth para asistentes conectados — Plan de implementación

**Goal:** Exponer un servidor MCP por tenant para que ChatGPT, Claude y Gemini consulten equipos, componentes, reportes y alertas del cliente mediante OAuth 2.1, con una interfaz no técnica para conectar y desconectar asistentes.

**Architecture:** `django-mcpz` 1.1.0 sirve MCP 2026-07-28 stateless sobre WSGI. La app `django_mcpz.oauth` implementa authorization code + PKCE, registro dinámico, refresh tokens y descubrimiento. Cada tenant tiene su propio authorization server y sus tokens viven en su schema. Las tools son de solo lectura y se filtran por la organización del usuario y sus permisos Django.

**Tech Stack:** Django 6.0, django-mcpz 1.1.0, msgspec, Django templates, Tailwind/TailAdmin, PostgreSQL multi-tenant (django-tenants), coverage.

**Spec:** `docs/superpowers/specs/` — decisión registrada en esta conversación (OAuth-only para asistentes hospedados).

## Global Constraints

- No introducir ASGI ni cambiar gunicorn/WSGI.
- No añadir tokens bearer manuales en esta etapa.
- Todas las tools son `read_only=True`; no hay escrituras.
- El aislamiento por tenant y por organización es obligatorio.
- La interfaz debe ser en español y comprensible para usuarios no técnicos.
- La cobertura global debe mantenerse en 85% o más.
- El comando de pruebas del repo es `docker compose exec django ...` (el servicio no se llama `web`).

## Review Focus

- Un token emitido para `https://tenant-a/mcp` no debe funcionar en `https://tenant-b/mcp`.
- Un usuario de una organización no debe ver equipos, reportes ni alertas de otra organización.
- Un usuario sin `reports.view_report` no debe ver ni ejecutar las tools de reportes.
- Un usuario sin organización no debe recibir acceso global accidental.
- El consentimiento debe mostrar el destino real de la redirección y no debe poder enviarse sin CSRF.

---

### Task 1: Dependencia y configuración OAuth

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `config/settings/base.py`
- Modify: `config/settings/production.py`
- Modify: `.env.example` (solo si hace falta documentar lifetimes)

**Interfaces:**
- Consumes: nothing.
- Produces: `django_mcpz`, `django_mcpz.oauth` and `apps.integrations` installed in `TENANT_APPS`.

- [x] Add `django-mcpz==1.1.0` to project dependencies.
- [x] Add `django_mcpz`, `django_mcpz.oauth`, and `apps.integrations` to `TENANT_APPS`.
- [x] Add `MCPZ_OAUTH_ACCESS_TOKEN_LIFETIME`, `MCPZ_OAUTH_REFRESH_TOKEN_LIFETIME`, `MCPZ_OAUTH_DYNAMIC_REGISTRATION`, `MCP_TOOL_DEFAULT_PAGE_SIZE`, `MCP_TOOL_MAX_PAGE_SIZE`.
- [x] Add the `django_mcpz.calls` logger in production.
- [x] Run `uv lock`.
- [x] Verify `python manage.py check --settings=config.settings.testing`.

### Task 2: Servidor MCP y tools

**Files:**
- Create: `apps/integrations/__init__.py`
- Create: `apps/integrations/apps.py`
- Create: `apps/integrations/mcp/__init__.py`
- Create: `apps/integrations/mcp/registry.py`
- Create: `apps/integrations/mcp/server.py`
- Create: `apps/integrations/mcp/schemas.py`
- Create: `apps/integrations/mcp/permissions.py`
- Create: `apps/integrations/mcp/tools/__init__.py`
- Create: `apps/integrations/mcp/tools/account.py`
- Create: `apps/integrations/mcp/tools/equipment.py`
- Create: `apps/integrations/mcp/tools/reports.py`
- Create: `apps/integrations/mcp/tools/alerts.py`
- Create: `apps/integrations/tests/__init__.py`
- Create: `apps/integrations/tests/base.py`
- Create: `apps/integrations/tests/test_tools.py`

**Interfaces:**
- Consumes: `oauth_auth` from `django_mcpz.oauth.auth`; `scope_queryset` from `apps.organizations.scoping`.
- Produces: a module-level `server` object and tools `get_account_overview`, `list_equipment`, `get_equipment`, `list_components`, `list_reports`, `get_report`, `list_alerts`, `get_alert`.

- [x] Create the `MCPServer` with `oauth_auth`, Spanish instructions and the platform icon.
- [x] Define msgspec param/result structs for every tool.
- [x] Scope every queryset by `request.user.organization` and reject users without an organization (except superusers).
- [x] Guard each domain tool with its Django permission.
- [x] Add tests for tenant/org isolation, permission filtering, pagination, filters and not-found errors.

### Task 3: URLs, OAuth endpoints and discovery

**Files:**
- Modify: `config/urls.py`
- Create: `apps/integrations/urls.py`
- Create: `apps/integrations/tests/test_oauth_flow.py`

**Interfaces:**
- Consumes: `server` from `apps.integrations.mcp`.
- Produces: `/mcp`, `/oauth/*`, `/.well-known/oauth-*`, `/integrations/mcp/`.

- [x] Route `path("mcp", server)` without a trailing slash.
- [x] Include `django_mcpz.oauth.urls` under `/oauth/`.
- [x] Include `django_mcpz.oauth.wellknown` at the site root.
- [x] Add `path("integrations/", include("apps.integrations.urls"))`.
- [x] Test discovery documents per tenant, dynamic registration, authorize, token exchange, refresh and revoke.
- [x] Test that an access token from tenant A is rejected on tenant B.
- [x] Test both 2026-07-28 and legacy 2025 protocol requests.

### Task 4: Consent page

**Files:**
- Create: `templates/django_mcpz/oauth/base.html`
- Create: `templates/django_mcpz/oauth/authorize.html`
- Create: `templates/django_mcpz/oauth/error.html`
- Create: `apps/integrations/tests/test_consent.py`

**Interfaces:**
- Consumes: context from `django_mcpz.oauth.views.authorize`: `user`, `client`, `redirect_uri`, `redirect_host`, `redirect_is_local`, `resource`, `server_title`, `scope`.
- Produces: a Spanish, branded consent page with `decision=allow|deny`.

- [x] Extend `layouts/home.html` and show tenant logo/name.
- [x] Show assistant name, user email, redirect host and role-based data summary.
- [x] Keep the form posting to the current URL with CSRF and `decision`.
- [x] Override the error page with a friendly Spanish message.
- [x] Test content, CSRF enforcement, allow and deny.

### Task 5: Login context

**Files:**
- Modify: `templates/account/login.html`
- Create: `apps/integrations/tests/test_login_context.py`

**Interfaces:**
- Consumes: `next` query parameter from the OAuth authorize redirect.
- Produces: a login page that preserves `next` and explains the connection flow.

- [x] Hide the disabled “Sign Up” link and show the contact message.
- [x] Show “Inicia sesión para conectar tu asistente” when `next` points to `/oauth/authorize`.
- [x] Verify the hidden `next` field is rendered.

### Task 6: Connected assistants UI

**Files:**
- Create: `apps/integrations/services.py`
- Create: `apps/integrations/views.py`
- Create: `apps/integrations/urls.py`
- Create: `templates/integrations/connected_apps.html`
- Modify: `templates/includes/aside.html`
- Modify: `templates/includes/navbar.html`
- Create: `apps/integrations/tests/test_connected_apps.py`

**Interfaces:**
- Consumes: `Client`, `AccessToken`, `RefreshToken`, `AuthorizationCode` from `django_mcpz.oauth.models`.
- Produces: `MCPConnectionService.connections_for_user()` and `disconnect()`, plus `/integrations/mcp/`.

- [x] List active, expired and revoked connections grouped by client.
- [x] Show the tenant MCP URL with a copy button.
- [x] Add ChatGPT/Claude/Gemini instructions using generic “add custom connector” language.
- [x] Disconnect revokes access tokens, refresh tokens and pending codes.
- [x] Add navigation entries in the sidebar and user menu.
- [x] Test ownership, grouping, status and revocation.

### Task 7: OAuth cleanup command

**Files:**
- Create: `apps/integrations/management/__init__.py`
- Create: `apps/integrations/management/commands/__init__.py`
- Create: `apps/integrations/management/commands/clear_mcp_oauth.py`
- Create: `apps/integrations/tests/test_commands.py`

**Interfaces:**
- Consumes: `django_mcpz.oauth.cleanup.clear_expired`.
- Produces: `python manage.py clear_mcp_oauth` across every tenant schema.

- [x] Iterate all non-public tenants and call `clear_expired()` inside each schema.
- [x] Restore the original tenant in a `finally` block.
- [x] Test with expired/revoked/active tokens in two tenants.

### Task 8: Remove unused code

**Files:**
- Modify: `pyproject.toml`
- Modify: `config/settings/base.py`
- Delete: `apps/core/pagination.py`
- Delete: `apps/core/tests/test_pagination.py`

**Interfaces:**
- Consumes: nothing.
- Produces: no DRF, authtoken, sesame or dead DRF pagination left.

- [x] Remove `rest_framework`, `rest_framework.authtoken` and `sesame` from `TENANT_APPS`.
- [x] Remove the `REST_FRAMEWORK` settings block.
- [x] Remove `djangorestframework` and `django-sesame` from dependencies.
- [x] Delete the unused DRF pagination module and its test.
- [x] Verify with `grep` and the full suite. Do not drop existing database tables.

### Task 9: Documentation and final validation

**Files:**
- Create: `docs/mcp.md`
- Modify: `README.md`

- [x] Document the OAuth flow, tenant URL, consent, connected apps, scopes, security and cleanup.
- [x] Run the full suite with coverage and the 85% gate.
- [x] Run `ruff check` and `ruff format --check`.
- [x] Run `django-reviewer` over the diff, apply findings and rerun the suite.

## Post-review fixes

The review found cross-module authorization gaps that the initial tests did not
cover. They were fixed and locked with regression tests:

- `get_equipment` no longer returns the last report without
  `reports.view_report`, nor the open-alert count without `alerts.view_alert`.
- `get_report` no longer returns alert rows without `alerts.view_alert`.
- `get_account_overview` only counts equipment, reports and alerts when the
  caller has the corresponding module permission.
- The cross-tenant test now provisions a second real tenant and asserts that a
  token issued in the first schema is rejected with `401`.
- The connected-assistants tests cover revoked connections as inactive.
