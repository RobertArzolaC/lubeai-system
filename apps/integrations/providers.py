"""Connection guides for the AI assistants supported by the MCP server.

The page at ``integrations/mcp/`` renders this catalog instead of hardcoding
each provider's menu. Keeping the steps in one place makes it possible to
verify them against the provider documentation and to test them without a
browser.

The menu labels were verified on 2026-10-21 against:
- ChatGPT: OpenAI Help Center, "Conectar servidores MCP personalizados".
- Claude: Anthropic Help Center, "Use connectors to extend Claude's
  capabilities" (Custom connectors).
- Gemini: Google Gemini Apps Help, "Connect & manage custom apps".

Provider interfaces change often, so the labels include the English name in
parentheses when the provider may show its UI in English.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils.translation import gettext_lazy as _

from apps.integrations.constants import MCP_SERVER_DESCRIPTION, MCP_SERVER_TITLE

CHATGPT_DOCS_URL = (
    "https://help.openai.com/es-419/articles/12584461-connecting-custom-mcp-servers-in-chatgpt"
)
CLAUDE_DOCS_URL = (
    "https://support.claude.com/en/articles/"
    "11175166-get-started-with-custom-connectors-using-remote-mcp"
)
GEMINI_DOCS_URL = "https://support.google.com/gemini/answer/17209137?hl=es"


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
    notes: tuple[str, ...] = field(default_factory=tuple)


def provider_guides(mcp_url: str) -> tuple[MCPProviderGuide, ...]:
    """Return the connection guides for the supported assistants.

    Args:
        mcp_url: The canonical MCP server URL for the current tenant.

    Returns:
        The guides in the order shown on the page: ChatGPT, Claude and Gemini.
    """
    return (
        MCPProviderGuide(
            slug="chatgpt",
            name="ChatGPT",
            icon="bot",
            summary=_(
                "Añade LubeAI como complemento MCP personalizado en ChatGPT."
            ),
            availability=_(
                "Web · Business, Enterprise o Edu; Pro con lectura"
            ),
            steps=(
                ProviderStep(
                    title=_("Abre Complementos"),
                    detail=_(
                        "En chatgpt.com, inicia sesión y entra a Complementos "
                        "desde el menú lateral."
                    ),
                ),
                ProviderStep(
                    title=_("Agregar servidor MCP personalizado"),
                    detail=_(
                        "Pulsa el botón + y selecciona esta opción."
                    ),
                ),
                ProviderStep(
                    title=_("Completa el formulario"),
                    detail=_(
                        "Configura la autenticación OAuth y acepta la advertencia "
                        "de riesgo antes de crear el complemento."
                    ),
                    fields=(
                        ProviderField(
                            label=_("Foto"),
                            hint=_("Opcional. Puedes subir el logo de LubeAI."),
                            copyable=False,
                        ),
                        ProviderField(
                            label=_("Nombre"),
                            value=MCP_SERVER_TITLE,
                        ),
                        ProviderField(
                            label=_("Descripción"),
                            value=MCP_SERVER_DESCRIPTION,
                        ),
                        ProviderField(
                            label=_("Conexión (URL)"),
                            value=mcp_url,
                            hint=_("Pégala tal cual, sin barra final."),
                        ),
                    ),
                ),
                ProviderStep(
                    title=_("Crea el complemento"),
                    detail=_(
                        "Pulsa Crear como complemento y revisa las herramientas "
                        "que ChatGPT detectó."
                    ),
                ),
            ),
            docs_url=CHATGPT_DOCS_URL,
            notes=(
                _(
                    "Solo puedes crearlo desde la web de ChatGPT; en la app "
                    "móvil no aparece la opción."
                ),
                _(
                    "El administrador del espacio de trabajo debe habilitar "
                    "«Crear complementos con MCP»."
                ),
                _(
                    "Después de crearlo, escribe @ en el chat y selecciona el "
                    "complemento."
                ),
            ),
        ),
        MCPProviderGuide(
            slug="claude",
            name="Claude",
            icon="sparkles",
            summary=_("Agrega LubeAI como conector personalizado con OAuth."),
            availability=_(
                "Web y escritorio · Gratis (1 conector), Pro, Max, Team y Enterprise"
            ),
            steps=(
                ProviderStep(
                    title=_("Abre Configuración"),
                    detail=_(
                        "En claude.ai, inicia sesión y entra a Configuración "
                        "(Customize)."
                    ),
                ),
                ProviderStep(
                    title=_("Entra a Conectores"),
                    detail=_("Abre Conectores (Connectors)."),
                ),
                ProviderStep(
                    title=_("Pulsa Agregar +"),
                    detail=_("Usa el botón + que está junto a Conectores."),
                ),
                ProviderStep(
                    title=_("Elige Agregar conector personalizado"),
                    detail=_(
                        "Selecciona Personalizado → Web (Custom → Web) y "
                        "completa los datos."
                    ),
                    fields=(
                        ProviderField(
                            label=_("Nombre"),
                            value=MCP_SERVER_TITLE,
                        ),
                        ProviderField(
                            label=_("URL del servidor MCP"),
                            value=mcp_url,
                            hint=_("Pégala tal cual, sin barra final."),
                        ),
                    ),
                ),
                ProviderStep(
                    title=_("Autoriza el acceso"),
                    detail=_(
                        "Revisa la autenticación detectada, elige Iniciar sesión "
                        "ahora (Sign in now) y deja el cliente OAuth recomendado. "
                        "Pulsa Agregar y completa el inicio de sesión en LubeAI."
                    ),
                ),
            ),
            docs_url=CLAUDE_DOCS_URL,
            notes=(
                _(
                    "En planes Team y Enterprise, un Owner debe habilitar el "
                    "conector en Configuración de la organización → Conectores."
                ),
                _("El plan gratuito permite un solo conector personalizado."),
                _(
                    "La conexión se realiza desde la nube de Claude; el servidor "
                    "debe ser accesible por HTTPS."
                ),
            ),
        ),
        MCPProviderGuide(
            slug="gemini",
            name="Gemini",
            icon="gem",
            summary=_(
                "Conecta LubeAI como aplicación personalizada en Gemini."
            ),
            availability=_("Solo web · Cuenta personal, EE. UU. e inglés"),
            steps=(
                ProviderStep(
                    title=_("Abre Ajustes"),
                    detail=_(
                        "En gemini.google.com, inicia sesión con una cuenta "
                        "personal de Google y abre Ajustes."
                    ),
                ),
                ProviderStep(
                    title=_("Entra a Inteligencia Personalizada"),
                    detail=_(
                        "Selecciona Inteligencia Personalizada (Personal "
                        "Intelligence)."
                    ),
                ),
                ProviderStep(
                    title=_("Pulsa Personalizado +"),
                    detail=_(
                        "En Personalizado (Custom apps), pulsa +. Si no ves esa "
                        "opción, entra a Aplicaciones conectadas (Connected Apps)."
                    ),
                    fields=(
                        ProviderField(
                            label=_("URL del servidor MCP"),
                            value=mcp_url,
                            hint=_("Pégala tal cual, sin barra final."),
                        ),
                    ),
                ),
                ProviderStep(
                    title=_("Autoriza el acceso"),
                    detail=_(
                        "Pulsa Siguiente y completa el inicio de sesión. Luego "
                        "escribe @ en el chat para invocar la aplicación."
                    ),
                ),
            ),
            docs_url=GEMINI_DOCS_URL,
            notes=(
                _(
                    "Solo puedes conectar desde la web; después queda disponible "
                    "en la app móvil."
                ),
                _(
                    "Requiere cuenta personal, tener 18 años o más, estar en "
                    "Estados Unidos, usar inglés y tener Keep Activity activo."
                ),
                _("Google no controla ni audita los servidores MCP de terceros."),
            ),
        ),
    )
