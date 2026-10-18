"""Tenant-aware wiring for easy-audit's request events.

easy-audit logs its ``RequestEvent`` from Django's ``request_started`` signal,
which fires **before** ``TenantMainMiddleware`` selects the schema for the
request. Its handler would then write the event into whichever schema was left
on the connection — ``public`` right after process start, where
``easyaudit_requestevent`` does not exist, so the very first request fails.

This receiver resolves the tenant from the request host first, leaves the
connection on that schema and then delegates to easy-audit's own handler. The
public schema has no ``easyaudit_requestevent`` table (no business data lives in
public), so requests served there are not audited; a host that matches no
``Domain`` is not audited either.

The receiver connects with easy-audit's ``dispatch_uid`` on purpose: it must win
over easy-audit's own handler, which is why ``apps.tenancy`` has to be listed
before ``easyaudit`` in ``INSTALLED_APPS``. With the same ``dispatch_uid``,
easy-audit's later connection is ignored and this one stays the only receiver.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.signals import request_started
from django.db import connection
from django_tenants.utils import (
    get_public_schema_name,
    get_tenant_domain_model,
    remove_www,
)

# easy-audit's own dispatch_uid for the receiver this module replaces.
DISPATCH_UID = "easy_audit_signals_request_started"


def request_started_handler(sender: Any, **kwargs: Any) -> None:
    """Select the request's tenant before easy-audit logs the request.

    Args:
        sender: The signal sender (the request class).
        **kwargs: Signal arguments; ``environ`` or ``scope`` carries the host.
    """
    host = _host_from_signal(kwargs)
    if not host:
        return

    connection.set_schema_to_public()
    domain = (
        get_tenant_domain_model()
        .objects.select_related("tenant")
        .filter(domain=remove_www(host.split(":")[0]))
        .first()
    )
    if domain is None:
        return

    connection.set_tenant(domain.tenant)
    if domain.tenant.schema_name == get_public_schema_name():
        # No ``easyaudit_requestevent`` in public: audit is a tenant concern.
        return
    if not getattr(settings, "DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS", False):
        return

    from easyaudit.signals.request_signals import (
        request_started_handler as audit_request_handler,
    )

    audit_request_handler(sender, **kwargs)


def _host_from_signal(kwargs: dict[str, Any]) -> str | None:
    """Return the request host carried by the signal, if any.

    Args:
        kwargs: Signal arguments.

    Returns:
        The host name, or ``None`` when the signal has no request context.
    """
    environ = kwargs.get("environ")
    if environ:
        return environ.get("HTTP_HOST") or environ.get("SERVER_NAME")

    scope = kwargs.get("scope")
    if scope:
        host = dict(scope.get("headers", [])).get(b"host")
        return host.decode() if isinstance(host, bytes) else None
    return None


def connect() -> None:
    """Subscribe the tenant resolver to ``request_started`` (idempotent)."""
    if not getattr(settings, "DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS", False):
        return
    # Same ``dispatch_uid`` as easy-audit's receiver: whichever connects first
    # wins, and the other is ignored. Disconnecting first keeps this module the
    # winner even if easy-audit's ``ready`` ran before this one.
    request_started.disconnect(dispatch_uid=DISPATCH_UID)
    request_started.connect(request_started_handler, dispatch_uid=DISPATCH_UID)
