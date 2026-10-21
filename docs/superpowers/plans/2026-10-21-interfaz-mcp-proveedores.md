# Corrección de la interfaz MCP y guías por proveedor — Plan de implementación

> **Para el agente ejecutor:** usar `superpowers:executing-plans` o `superpowers:subagent-driven-development`. Los pasos usan checkbox (`- [ ]`).

**Goal:** Que la pantalla **Integraciones → Asistentes conectados** muestre pasos verificados y en español para conectar ChatGPT, Claude y Gemini, respaldados por un catálogo único en el backend y por `docs/ia.md`.

**Architecture:** Un módulo declarativo `apps/integrations/providers.py` define los pasos, campos y notas de cada proveedor. La vista inyecta ese catálogo (con la URL MCP del tenant) en el contexto y la plantilla lo renderiza con un acordeón por proveedor. Las constantes de identidad del servidor MCP se comparten con el registro para evitar duplicar nombre y descripción. La guía humana vive en `docs/ia.md`.

**Tech Stack:** Django 6.0, plantillas Django, Tailwind/TailAdmin, Lucide, JavaScript nativo, `django-mcpz` 1.1.0, tests con `unittest`/Django TestCase.

**Spec:** Conversación del 21/10/2026 + documentación oficial verificada:
- ChatGPT: https://help.openai.com/es-419/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- Claude: https://support.claude.com/en/articles/11176164-pre-built-web-connectors (sección *Custom connectors*)
- Gemini: https://support.google.com/gemini/answer/17209137

## Global Constraints

- Todo el texto visible para el usuario va en **español**. Los nombres de menús que el proveedor muestra en inglés se incluyen entre paréntesis.
- No se agregan dependencias nuevas.
- El flujo OAuth, los endpoints `/mcp`, `/oauth/*` y los permisos no cambian.
- La pantalla sigue usando el layout `layouts/dashboard.html`, los tokens de color de TailAdmin y los iconos Lucide existentes.
- Toda función y clase nueva lleva type hints y docstring PEP 257.
- Los tests nuevos usan el estilo del proyecto (`django.test.TestCase` o `SimpleTestCase` cuando no se toca la base de datos).
- No se modifica el comportamiento de desconexión ni de listado de conexiones; solo se eliminan campos que la plantilla no consume.

## Review Focus

1. **Etiquetas de menú desactualizadas:** cada proveedor cambia su UI; los pasos deben coincidir con la interfaz verificada y no con una versión anterior. Test: el HTML contiene las rutas exactas de los tres proveedores.
2. **URL MCP con barra final o host equivocado:** la URL inyectada debe ser la del tenant actual, sin barra final. Test: aparece `resource_url()` y no una URL fija.
3. **Gemini restringido por cuenta/región:** la pantalla debe advertir que solo funciona con cuenta personal, EE. UU., inglés y Keep Activity. Test: el texto de requisitos está presente.
4. **Usuario sin organización o sin módulos:** la pantalla debe seguir mostrando los pasos y la advertencia, sin romper. Test: usuario sin organización ve la advertencia y las guías.
5. **Copiado en contextos sin Clipboard API:** el botón debe fallar con un mensaje claro y no lanzar una excepción no controlada. Test: la plantilla incluye el bloque `try/catch` y los botones usan `data-copy-value`.

---

### Task 1: Catálogo de proveedores y constantes del servidor

**Files:**
- Create: `apps/integrations/constants.py`
- Create: `apps/integrations/providers.py`
- Modify: `apps/integrations/mcp/registry.py:13-26`
- Test: `apps/integrations/tests/test_providers.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `MCP_SERVER_NAME: str = "lubeai"`
  - `MCP_SERVER_TITLE: str = "LubeAI"`
  - `MCP_SERVER_DESCRIPTION: str = "Consulta de equipos, reportes y alertas de lubricación."`
  - `ProviderField(label: str, value: str = "", hint: str = "", copyable: bool = True)`
  - `ProviderStep(title: str, detail: str = "", fields: tuple[ProviderField, ...] = ())`
  - `MCPProviderGuide(slug, name, icon, summary, availability, steps, docs_url, notes)`
  - `provider_guides(mcp_url: str) -> tuple[MCPProviderGuide, ...]` con el orden ChatGPT, Claude, Gemini.

- [ ] **Step 1: Escribir los tests del catálogo**

```python
"""Tests for the provider connection guides."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.integrations.providers import provider_guides

MCP_URL = "https://demo.test/mcp"


class ProviderGuideTests(SimpleTestCase):
    """The catalog is the single source for the connection steps."""

    def test_guides_are_ordered_and_complete(self) -> None:
        """ChatGPT, Claude and Gemini are present with steps and docs."""
        guides = provider_guides(MCP_URL)
        self.assertEqual([guide.slug for guide in guides], ["chatgpt", "claude", "gemini"])
        for guide in guides:
            self.assertTrue(guide.name)
            self.assertTrue(guide.summary)
            self.assertTrue(guide.steps)
            self.assertTrue(guide.docs_url.startswith("https://"))

    def test_url_is_injected_in_every_guide(self) -> None:
        """The tenant MCP URL appears in every provider's fields."""
        guides = provider_guides(MCP_URL)
        for guide in guides:
            values = [
                field.value
                for step in guide.steps
                for field in step.fields
                if field.copyable
            ]
            self.assertIn(MCP_URL, values)

    def test_provider_steps_match_the_documented_menus(self) -> None:
        """Each guide contains the labels verified in the provider UI."""
        guides = {guide.slug: guide for guide in provider_guides(MCP_URL)}

        chatgpt = " ".join(step.title for step in guides["chatgpt"].steps)
        self.assertIn("Complementos", chatgpt)
        self.assertIn("Agregar servidor MCP personalizado", chatgpt)

        claude = " ".join(step.title for step in guides["claude"].steps)
        self.assertIn("Conectores", claude)
        self.assertIn("Agregar conector personalizado", claude)

        gemini = " ".join(step.title for step in guides["gemini"].steps)
        self.assertIn("Inteligencia Personalizada", gemini)
        self.assertIn("Personalizado", gemini)
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run python manage.py test apps.integrations.tests.test_providers --settings=config.settings.testing`
Expected: FAIL con `ModuleNotFoundError: No module named 'apps.integrations.providers'`.

- [ ] **Step 3: Crear `apps/integrations/constants.py`**

```python
"""Shared identity constants for the MCP server and its connection guides."""

from __future__ import annotations

MCP_SERVER_NAME = "lubeai"
MCP_SERVER_TITLE = "LubeAI"
MCP_SERVER_DESCRIPTION = "Consulta de equipos, reportes y alertas de lubricación."
```

- [ ] **Step 4: Crear `apps/integrations/providers.py`**

Definir los tres dataclasses con `gettext_lazy` para los textos visibles. El catálogo debe respetar exactamente esta estructura:

- ChatGPT: `Complementos` → `Agregar +` → `Agregar servidor MCP personalizado` con campos `Foto` (opcional, no copiable), `Nombre` = `MCP_SERVER_TITLE`, `Descripción` = `MCP_SERVER_DESCRIPTION`, `Conexión (URL)` = `mcp_url`; luego `Crear como complemento`.
- Claude: `Configuración` (Customize) → `Conectores` → `Agregar +` → `Agregar conector personalizado` con campos `Nombre` y `URL del servidor MCP`; luego `Autorizar el acceso`.
- Gemini: `Ajustes` → `Inteligencia Personalizada` → `Personalizado +` con campo `URL del servidor MCP`; luego `Autoriza el acceso`.

Cada guía incluye `availability` y `notes` con estas advertencias verificadas:

- ChatGPT: solo web; Business/Enterprise/Edu con MCP completo, Pro con lectura; el administrador debe permitir “Crear complementos con MCP”.
- Claude: gratis limitado a 1 conector personalizado; en Team/Enterprise un Owner debe habilitarlo; web/escritorio, móvil en beta.
- Gemini: solo web para conectar; cuenta personal, 18+, EE. UU., inglés y Keep Activity activo; luego disponible en móvil.

Firmas exactas:

```python
@dataclass(frozen=True)
class ProviderField:
    """One form field the assistant asks for."""

    label: str
    value: str = ""
    hint: str = ""
    copyable: bool = True


@dataclass(frozen=True)
class ProviderStep:
    """One step in a provider's connection flow."""

    title: str
    detail: str = ""
    fields: tuple[ProviderField, ...] = ()


@dataclass(frozen=True)
class MCPProviderGuide:
    """Everything the page needs to render one assistant's guide."""

    slug: str
    name: str
    icon: str
    summary: str
    availability: str
    steps: tuple[ProviderStep, ...]
    docs_url: str
    notes: tuple[str, ...] = ()


def provider_guides(mcp_url: str) -> tuple[MCPProviderGuide, ...]:
    """Return the connection guides for the supported assistants."""
```

- [ ] **Step 5: Reutilizar las constantes en `registry.py`**

Cambiar `name`, `title` y `description` para importar desde `apps.integrations.constants`. Mantener el mismo `version`, `icons` y `auth`. Aprovechar para ampliar `instructions` en español con el orden de herramientas (`get_account_overview`, listados, detalles), la naturaleza de solo lectura, el alcance por organización y la instrucción de responder en el idioma del usuario.

- [ ] **Step 6: Ejecutar los tests**

Run: `uv run python manage.py test apps.integrations.tests.test_providers --settings=config.settings.testing`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/integrations/constants.py apps/integrations/providers.py apps/integrations/mcp/registry.py apps/integrations/tests/test_providers.py
git commit -m "feat(integrations): add verified MCP provider guides"
```

---

### Task 2: Vista y plantilla de Asistentes conectados

**Files:**
- Modify: `apps/integrations/views.py:27-51`
- Modify: `templates/integrations/connected_apps.html:32-114` y bloque `extra_js`
- Test: `apps/integrations/tests/test_connected_apps.py`

**Interfaces:**
- Consumes: `provider_guides(mcp_url)` de Task 1.
- Produces: contexto `providers` con `tuple[MCPProviderGuide, ...]`.

- [ ] **Step 1: Añadir tests de la pantalla**

Agregar a `ConnectedAppsTests`:

```python
def test_page_renders_verified_provider_steps(self) -> None:
    """The page shows the current menu path for each provider."""
    self.client.force_login(self.user)
    response = self.client.get(self.url)
    self.assertContains(response, "Complementos")
    self.assertContains(response, "Agregar servidor MCP personalizado")
    self.assertContains(response, "Agregar conector personalizado")
    self.assertContains(response, "Inteligencia Personalizada")
    self.assertContains(response, "Personalizado")

def test_page_renders_copyable_server_identity(self) -> None:
    """The suggested name and description are ready to copy."""
    self.client.force_login(self.user)
    response = self.client.get(self.url)
    self.assertContains(response, "LubeAI")
    self.assertContains(response, "Consulta de equipos, reportes y alertas de lubricación.")

def test_page_renders_guides_without_organization(self) -> None:
    """Users without an organization still see the steps and the warning."""
    user = user_factories.UserFactory(organization=None)
    self.client.force_login(user)
    response = self.client.get(self.url)
    self.assertContains(response, "no tiene una organización asignada")
    self.assertContains(response, "Agregar servidor MCP personalizado")
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run python manage.py test apps.integrations.tests.test_connected_apps --settings=config.settings.testing`
Expected: FAIL en los nuevos tests porque la plantilla aún tiene los textos antiguos.

- [ ] **Step 3: Inyectar el catálogo en la vista**

En `ConnectedAppsView.get_context_data`, importar `provider_guides` y añadir:

```python
"providers": provider_guides(resource),
```

Mantener `mcp_url`, `connections`, `has_organization` y `has_any_module` sin cambios.

- [ ] **Step 4: Reemplazar el bloque “2. Añádela en tu asistente”**

Sustituir los tres `<details>` hardcodeados por un `{% for provider in providers %}`. Cada tarjeta debe incluir:

- `summary` con icono Lucide (`provider.icon`), nombre, badge de `provider.availability` y chevron.
- `provider.summary` como introducción.
- `<ol>` de pasos con marcador numérico; para cada `step.fields`, una lista de definición con etiqueta, valor copiable y `hint`.
- Botones `data-copy-value="{{ field.value }}"` y `aria-label="Copiar {{ field.label }}"`.
- Notas de `provider.notes` con icono `info`.
- Enlace `provider.docs_url` con `target="_blank"` y `rel="noopener noreferrer"`, texto “Ver guía oficial”.

El primer proveedor se muestra abierto (`{% if forloop.first %}open{% endif %}`). Mantener las tarjetas 1 (URL) y 3 (autorización), la columna de conexiones y la tarjeta de seguridad.

- [ ] **Step 5: Unificar el JavaScript de copiado**

Reemplazar el listener del botón `copy-mcp-url` por un listener genérico:

```javascript
document.querySelectorAll('[data-copy-value]').forEach((button) => {
    button.addEventListener('click', async () => {
        const value = button.getAttribute('data-copy-value');
        if (!value) return;
        try {
            await navigator.clipboard.writeText(value);
            showAlert('', '{% trans "Copiado." %}', 'success');
        } catch (error) {
            showAlert('{% trans "Error" %}', '{% trans "No se pudo copiar. Selecciona el texto manualmente." %}', 'error');
        }
    });
});
```

El botón principal de la URL usa el mismo atributo. No dejar IDs ni listeners duplicados.

- [ ] **Step 6: Ejecutar los tests de la pantalla**

Run: `uv run python manage.py test apps.integrations.tests.test_connected_apps --settings=config.settings.testing`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/integrations/views.py templates/integrations/connected_apps.html apps/integrations/tests/test_connected_apps.py
git commit -m "feat(integrations): render provider-specific MCP connection steps"
```

---

### Task 3: Actualizar `docs/ia.md` y el README

**Files:**
- Modify: `docs/ia.md`
- Modify: `README.md:87-101`

**Interfaces:**
- Consumes: el contenido de Task 1 (mismos pasos y advertencias).
- Produces: guía humana en español.

- [ ] **Step 1: Reescribir `docs/ia.md`**

Estructura obligatoria:

1. Título y fecha de verificación (`21/10/2026`).
2. **Antes de empezar**: URL `https://<tenant>/mcp` sin barra final, organización/permisos, OAuth, solo lectura.
3. **ChatGPT**: requisitos, pasos `Complementos → Agregar + → Agregar servidor MCP personalizado` con los campos Foto/Nombre/Descripción/Conexión (URL), autorización, verificación con `@` y límites por plan.
4. **Claude**: requisitos, pasos `Configuración → Conectores → Agregar + → Agregar conector personalizado` con Nombre/URL, autenticación OAuth, habilitación en Team/Enterprise y límite de 1 conector en el plan gratis.
5. **Gemini**: requisitos, pasos `Ajustes → Inteligencia Personalizada → Personalizado +` con URL, autorización, uso con `@`, y restricciones (cuenta personal, 18+, EE. UU., inglés, Keep Activity, solo web para conectar).
6. **Cómo verificar la conexión**: prompts de ejemplo y qué hacer si no aparecen herramientas.
7. **Cómo desconectar**: desde LubeAI y desde cada proveedor.
8. **Problemas frecuentes**: opción que no aparece, error de autorización, URL con barra final, usuario sin módulos.
9. **Fuentes oficiales** con los tres enlaces.

Incluir los nombres en inglés entre paréntesis cuando la interfaz del proveedor pueda aparecer en inglés.

- [ ] **Step 2: Corregir el enlace roto del README**

En `README.md`, cambiar `[docs/mcp.md](docs/mcp.md)` por `[docs/ia.md](docs/ia.md)`. Revisar que el resto de la sección siga siendo correcto.

- [ ] **Step 3: Verificar que no quedan referencias al documento eliminado**

Run: `rg -n "docs/mcp\\.md" . --glob '!*.pyc' --glob '!.venv/**'`
Expected: sin resultados.

- [ ] **Step 4: Commit**

```bash
git add docs/ia.md README.md
git commit -m "docs(integrations): document verified assistant connection steps"
```

---

### Task 4: Eliminar código sin uso

**Files:**
- Modify: `apps/integrations/services.py:24-146`
- Modify: `apps/integrations/mcp/permissions.py:62-64`

**Interfaces:**
- Consumes: nada.
- Produces: `MCPConnection` sin `scope`, `access_token_count` ni `refresh_token_count`; `disconnect()` sin valor de retorno; sin `display_name()`.

- [ ] **Step 1: Confirmar que los campos no se usan**

Run: `rg -n "access_token_count|refresh_token_count|display_name" apps templates`
Expected: solo las definiciones en `services.py` y `permissions.py`.

- [ ] **Step 2: Quitar los campos y su cálculo**

En `MCPConnection`, eliminar `scope`, `access_token_count` y `refresh_token_count`. En `connections_for_user`, eliminar la variable `scope`, los dos conteos y los argumentos correspondientes del constructor.

- [ ] **Step 3: Simplificar `disconnect()`**

Cambiar la firma a `def disconnect(self, user, client_id: int) -> None:` y eliminar el diccionario de retorno. Mantener la transacción, las actualizaciones y la excepción `Client.DoesNotExist`.

- [ ] **Step 4: Eliminar `display_name()`**

Borrarlo de `permissions.py`; no tiene consumidores.

- [ ] **Step 5: Ejecutar tests y lint**

Run:
```bash
uv run python manage.py test apps.integrations --settings=config.settings.testing
uv run ruff check apps/integrations
```
Expected: PASS y sin errores de lint.

- [ ] **Step 6: Commit**

```bash
git add apps/integrations/services.py apps/integrations/mcp/permissions.py
git commit -m "refactor(integrations): remove unused MCP connection data"
```

---

### Task 5: Revisión con `django-reviewer` y verificación final

**Files:**
- Revisar: todo el diff de las tareas 1–4.

- [ ] **Step 1: Ejecutar la suite completa de integraciones**

Run: `uv run python manage.py test apps.integrations --settings=config.settings.testing`
Expected: PASS.

- [ ] **Step 2: Ejecutar Ruff**

Run: `uv run ruff check apps/integrations config`
Expected: sin errores.

- [ ] **Step 3: Revisar con la skill `django-reviewer`**

Aplicar el checklist en modo report-only sobre el diff:
- ¿La vista sigue delgada y delega el catálogo?
- ¿Los textos visibles están en español y usan `gettext_lazy`?
- ¿Hay consultas N+1 nuevas? (No se esperan consultas nuevas).
- ¿Se preservó el comportamiento de desconexión y la autorización?
- ¿Quedaron imports, campos o funciones sin uso?
- ¿Los tests cubren los tres proveedores, la URL del tenant, el usuario sin organización y el copiado?

Corregir cualquier hallazgo dentro del alcance y volver a ejecutar los tests.

- [ ] **Step 4: Verificar la pantalla en el navegador**

Run: `uv run python manage.py runserver`
Revisar `/integrations/mcp/` en escritorio y móvil:
- El primer acordeón abre y los demás se expanden.
- Los botones copian URL, nombre y descripción.
- Las etiquetas de cada proveedor coinciden con `docs/ia.md`.
- El modo oscuro mantiene contraste y focos visibles.

- [ ] **Step 5: Commit final de ajustes de revisión**

```bash
git add -A
git commit -m "chore(integrations): address MCP interface review findings"
```
