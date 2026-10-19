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

That contract is third-party and could change silently: if easy-audit renames
its ``dispatch_uid``, its handler is no longer replaced and every request would
be written twice (two ``RequestEvent`` rows for one request). :func:`connect`
verifies the takeover instead of trusting it, and fails at start-up when the
replacement did not happen.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
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
    """Subscribe the tenant resolver to ``request_started`` (idempotent).

    easy-audit's receiver is imported first, so its own connection has run and
    the ``disconnect`` below has a deterministic result regardless of the order
    of ``INSTALLED_APPS``. Replacing it keeps a single receiver for every
    request: easy-audit's handler is not connected twice, it is only called by
    this module's receiver.

    Raises:
        ImproperlyConfigured: If no receiver is connected under
            :data:`DISPATCH_UID` once easy-audit's module has been imported.
            That means easy-audit renamed its ``dispatch_uid``, so its handler
            would run alongside this one and every request would produce two
            ``RequestEvent`` rows. Failing at start-up is deliberate: the
            duplicated audit rows are silent otherwise.
    """
    if not getattr(settings, "DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS", False):
        return

    # Importing the module runs easy-audit's own ``request_started`` connection.
    from easyaudit.signals import request_signals  # noqa: F401

    if not request_started.disconnect(dispatch_uid=DISPATCH_UID):
        raise ImproperlyConfigured(
            "easy-audit's request receiver is not connected under "
            f"{DISPATCH_UID!r}: its dispatch_uid probably changed. Update "
            "apps.tenancy.signals.DISPATCH_UID, otherwise easy-audit's own "
            "receiver runs next to this one and logs every request twice."
        )

    request_started.connect(request_started_handler, dispatch_uid=DISPATCH_UID)
