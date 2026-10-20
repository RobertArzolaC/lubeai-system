"""The project's MCP server object.

The server is intentionally stateless and synchronous: ``django-mcpz`` handles
the MCP 2026-07-28 protocol on top of a regular Django view, so the project
keeps its existing gunicorn/WSGI deployment.
"""

from __future__ import annotations

from django_mcpz.oauth.auth import oauth_auth
from django_mcpz.server import Icon, MCPServer

server = MCPServer(
    name="lubeai",
    title="LubeAI",
    version="1.0.0",
    description="Consulta de equipos, reportes y alertas de lubricación.",
    instructions=(
        "Este servidor expone datos de monitoreo de condición de equipos. "
        "Empieza con get_account_overview para conocer la organización y los "
        "módulos disponibles. Usa las tools de listado con filtros y paginación; "
        "no inventes identificadores. Toda la información es de solo lectura y "
        "está limitada a la organización del usuario autenticado."
    ),
    icons=[Icon(static="assets/images/logos/logo.png", sizes=("any",))],
    auth=oauth_auth,
)
