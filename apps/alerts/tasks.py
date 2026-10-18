"""Celery tasks for the alerts app.

Alerts are TENANT data: the ``alerts_alert`` table only exists inside a tenant
schema, and two clients may each own an alert with the same primary key. A
worker, on the other hand, starts on ``public``. Every task in this module
therefore fixes the schema of the work explicitly against the shared registry
of active tenants instead of relying on whatever search path the worker happens
to have: ``public`` is not a client, so it never runs there.
"""

from __future__ import annotations

from typing import Any

from celery import shared_task
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context

from apps.alerts.services.notifications import AlertNotificationService
from apps.tenancy import models as tenancy_models


@shared_task()
def send_alert_notifications_task(
    alert_ids: list[int], schema_name: str | None = None
) -> dict[str, Any]:
    """Notify recipients about new alerts, inside the tenant that owns them.

    Dispatched by the ``Alert`` ``post_save`` signal when an alert is created
    with ``CRITICAL`` or ``CAUTION`` severity in the ``OPEN`` state.

    Alert PKs are only unique *within a schema*, so the task must never run the
    same IDs in another client's schema: it could notify one client about a row
    that belongs to another. It walks the active tenant registry instead and
    runs the notification inside the matching schema, with an explicit
    ``schema_context``. An inactive or unknown schema — ``public`` included —
    gets no notification at all.

    Args:
        alert_ids: Alert PKs to notify about, as they exist in ``schema_name``.
        schema_name: Schema that owns the alerts. Defaults to the schema of the
            dispatching context, which ``django_tenants`` activates right
            before the task runs.

    Returns:
        A mapping ``{schema_name: service_result}`` with one entry per matching
        active tenant. Empty when no active tenant owns ``schema_name``.
    """
    target_schema = schema_name or connection.schema_name
    public_schema = get_public_schema_name()
    if not target_schema or target_schema == public_schema:
        return {}

    active_tenants = tenancy_models.Tenant.objects.filter(is_active=True).exclude(
        schema_name=public_schema
    )
    results: dict[str, Any] = {}
    for tenant in active_tenants:
        if tenant.schema_name != target_schema:
            continue
        with schema_context(tenant.schema_name):
            results[tenant.schema_name] = AlertNotificationService(alert_ids).send()
    return results
