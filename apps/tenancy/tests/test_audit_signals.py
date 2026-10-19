"""Tests for the tenant-aware wiring of easy-audit's request events.

easy-audit logs one ``RequestEvent`` per request from Django's
``request_started`` signal. Because that signal fires before the schema is
selected, ``apps.tenancy.signals`` replaces easy-audit's receiver (same
``dispatch_uid``) and delegates to it once the tenant is known. The contract is
third-party: if easy-audit renamed its ``dispatch_uid``, both receivers would
run and every request would be logged twice. These tests pin the takeover.
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.core.signals import request_started
from django.db import connection
from django.test import override_settings
from django_tenants.utils import get_public_schema_name, tenant_context
from easyaudit.models import RequestEvent
from easyaudit.signals.request_signals import (
    request_started_handler as audit_request_handler,
)

from apps.tenancy import signals
from apps.tenancy.tests.base import TenantProvisionTestCase


@override_settings(ALLOWED_HOSTS=["*"])
class AuditRequestSignalTests(TenantProvisionTestCase):
    """A tenant request produces exactly one ``RequestEvent``."""

    def setUp(self) -> None:
        """Leave the signal wiring as it was found after every test."""
        super().setUp()
        self.addCleanup(request_started.disconnect, dispatch_uid=signals.DISPATCH_UID)

    def test_tenant_request_produces_a_single_request_event(self) -> None:
        """A request to a tenant host leaves exactly one audit row.

        The production wiring is reproduced: easy-audit's own receiver is
        connected first under the shared ``dispatch_uid`` and then replaced, so
        a single receiver logs the request. Without the replacement this
        request would write two rows.
        """
        tenant = self.provision()
        host = tenant.get_primary_domain().domain

        with override_settings(DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS=True):
            request_started.connect(
                audit_request_handler, dispatch_uid=signals.DISPATCH_UID
            )
            signals.connect()

            self.client.get("/", HTTP_HOST=host)

        with tenant_context(tenant):
            self.assertEqual(RequestEvent.objects.count(), 1)
            self.assertEqual(RequestEvent.objects.get().url, "/")

    def test_connect_rejects_a_renamed_easy_audit_uid(self) -> None:
        """A renamed easy-audit ``dispatch_uid`` fails loudly at start-up.

        Without the replacement there would be two receivers and two audit rows
        per request, which is silent otherwise.
        """
        request_started.disconnect(dispatch_uid=signals.DISPATCH_UID)

        with (
            override_settings(DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS=True),
            self.assertRaises(ImproperlyConfigured),
        ):
            signals.connect()

        self.assertNotIn(
            signals.DISPATCH_UID,
            [lookup_key[0] for lookup_key, *_ in request_started.receivers],
        )


class RequestHostExtractionTests(TenantProvisionTestCase):
    """The resolver reads the host from either WSGI or ASGI signal kwargs."""

    def setUp(self) -> None:
        """Always start from a known schema."""
        super().setUp()
        connection.set_schema_to_public()

    def test_signal_without_a_request_context_is_ignored(self) -> None:
        """A signal with no host leaves the connection untouched."""
        signals.request_started_handler(None, environ={})

        self.assertEqual(connection.schema_name, get_public_schema_name())

    def test_asgi_scope_resolves_the_tenant(self) -> None:
        """An ASGI request selects the tenant of its host header."""
        self.provision()

        signals.request_started_handler(
            None, scope={"headers": [(b"host", b"acme.localhost")]}
        )

        self.assertEqual(connection.schema_name, "acme")

    def test_host_with_port_is_normalised(self) -> None:
        """The port is stripped before the domain is looked up."""
        self.provision()

        signals.request_started_handler(
            None, environ={"HTTP_HOST": "acme.localhost:8000"}
        )

        self.assertEqual(connection.schema_name, "acme")
