"""The project's MCP server object.

The server is intentionally stateless and synchronous: ``django-mcpz`` handles
the MCP 2026-07-28 protocol on top of a regular Django view, so the project
keeps its existing gunicorn/WSGI deployment.
"""

from __future__ import annotations

from django_mcpz.oauth.auth import oauth_auth
from django_mcpz.server import Icon, MCPServer

from apps.integrations.constants import (
    MCP_SERVER_DESCRIPTION,
    MCP_SERVER_NAME,
    MCP_SERVER_TITLE,
)

server = MCPServer(
    name=MCP_SERVER_NAME,
    title=MCP_SERVER_TITLE,
    version="1.0.0",
    description=MCP_SERVER_DESCRIPTION,
    instructions=(
        "Este servidor permite consultar, en modo de solo lectura, los equipos, "
        "componentes, reportes de laboratorio y alertas de la organización del "
        "usuario autenticado. Empieza siempre con get_account_overview para "
        "conocer la organización y los módulos disponibles. Usa list_equipment, "
        "list_components, list_reports y list_alerts con sus filtros y "
        "paginación; después get_equipment, get_report o get_alert para el "
        "detalle. No inventes identificadores ni datos: si una consulta no "
        "devuelve resultados, dilo. No puedes modificar información. Responde en "
        "el idioma del usuario y nunca reveles datos de otras organizaciones."
    ),
    icons=[Icon(static="assets/images/logos/logo.png", sizes=("any",))],
    auth=oauth_auth,
)
