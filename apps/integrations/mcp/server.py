"""Import the server and register every tool module."""

from apps.integrations.mcp.registry import server
from apps.integrations.mcp.tools import (  # noqa: F401
    account,
    alerts,
    equipment,
    reports,
)

__all__ = ["server"]
