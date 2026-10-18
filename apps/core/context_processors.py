"""Context processors for the core app."""

from __future__ import annotations

from typing import Any

from django.contrib.sites.shortcuts import get_current_site
from django.db import connection
from django_tenants.utils import get_public_schema_name


def site_processor(request: Any) -> dict[str, Any]:
    """Expose the current ``Site`` to every template as ``{{ site }}``.

    ``django.contrib.sites`` is a TENANT app, so its table only exists inside a
    tenant schema. Requests served on the ``public`` schema (the public landing
    page, and the error pages raised for a host with no tenant) have no ``Site``
    and get ``None`` instead of a database error.

    Args:
        request: The current HTTP request.

    Returns:
        Context with the current ``Site``, or ``None`` on the public schema.
    """
    if connection.schema_name == get_public_schema_name():
        return {"site": None}
    return {"site": get_current_site(request)}
