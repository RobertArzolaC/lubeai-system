"""System checks that protect the schema boundary.

The platform isolates clients with one PostgreSQL schema each. A database that
was deployed *before* the split still keeps the business (``TENANT_APPS``)
tables in ``public``: the tables are outside the ``<tenant>, public`` search
path of every tenant, so provisioning a tenant silently leaves the legacy rows
stranded. These checks turn that state into a loud failure instead of a silent
data loss.

The registry registering them happens in :meth:`apps.tenancy.apps.TenancyConfig.ready`.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Warning, register
from django.db import DatabaseError, InterfaceError, connection
from django_tenants.utils import get_public_schema_name

#: Business (``TENANT_APPS``) tables used as sentinels. Any of them living in
#: ``public`` is proof that the database predates the schema split; the list is
#: deliberately short (one table per business app) because the check only needs
#: a positive signal, not an exhaustive inventory.
LEGACY_PUBLIC_TABLES: tuple[str, ...] = (
    "users_user",
    "organizations_organization",
    "equipment_machine",
    "reports_report",
)

#: ``SHARED_APPS`` table whose presence marks the registry as migrated. Without
#: it the database is either brand new or mid-migration, and the check stays
#: quiet so it never blocks ``migrate`` on the first deploy.
REGISTRY_TABLE: str = "tenancy_tenant"

#: Operator-facing pointer to the procedure that fixes the situation.
RUNBOOK_HINT: str = (
    "Cut the legacy database over to the schema layout following "
    "docs/despliegue-multi-tenant.md (section 'Migrar una base legada')."
)


def _tables_in_public_schema() -> set[str]:
    """Return the tables that physically live in the ``public`` schema.

    The query names the schema explicitly, so it does not depend on the search
    path of the connection it runs on.

    Returns:
        The set of table names registered in ``public``.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s",
            [get_public_schema_name()],
        )
        return {row[0] for row in cursor.fetchall()}


@register()
def check_legacy_public_tables(
    app_configs: Any = None, **kwargs: Any
) -> list[Any]:
    """Report business tables stranded in the ``public`` schema.

    A legacy database is detected as "tenancy registry present *and* business
    tables in ``public``". It fails as an :class:`~django.core.checks.Error` in
    production (``DEBUG=False``) and as a :class:`~django.core.checks.Warning`
    in development, where the state is expected while migrating by hand.

    Args:
        app_configs: App configurations Django passes to every system check;
            unused because the check inspects the database, not the apps.
        **kwargs: Extra keyword arguments Django passes to system checks
            (``databases``, ``tags``); unused for the same reason.

    Returns:
        An empty list on a clean database, otherwise a single issue pointing at
        the cut-over runbook.
    """
    try:
        tables = _tables_in_public_schema()
    except (DatabaseError, InterfaceError):
        # No database yet (a fresh checkout, the first migrate) or a connection
        # that cannot answer: there is nothing to judge, so stay quiet.
        return []

    if REGISTRY_TABLE not in tables:
        return []

    legacy = sorted(tables.intersection(LEGACY_PUBLIC_TABLES))
    if not legacy:
        return []

    message = (
        "Legacy database detected: the business tables "
        f"{', '.join(legacy)} live in the 'public' schema while the tenancy "
        "registry already exists. Their rows are stranded outside every tenant "
        "and a newly provisioned tenant starts empty."
    )
    if settings.DEBUG:
        return [Warning(message, hint=RUNBOOK_HINT, id="tenancy.W001")]
    return [Error(message, hint=RUNBOOK_HINT, id="tenancy.E001")]
