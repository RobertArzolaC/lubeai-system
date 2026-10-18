"""Tests for the ``apps.core.context_processors`` module."""

from django.contrib.sites.models import Site
from django.db import connection
from django.test import RequestFactory, TestCase

from apps.core.context_processors import site_processor
from apps.core.tests.base import TenantSchemaTestCase


class SiteProcessorPublicSchemaTests(TestCase):
    """The processor must not touch ``django_site`` outside a tenant schema.

    ``django.contrib.sites`` is a TENANT app, so its table does not exist in the
    ``public`` schema. Requests there — the public landing page and the error
    pages of a host with no tenant — must degrade instead of raising.
    """

    def setUp(self) -> None:
        # The processor branches on the connection's schema: pin the precondition
        # instead of relying on a previous test class resetting it.
        connection.set_schema_to_public()
        self.request = RequestFactory().get("/")

    def test_returns_no_site_on_the_public_schema(self) -> None:
        """A request outside a tenant gets ``None`` under the ``site`` key."""
        context = site_processor(self.request)
        self.assertIn("site", context)
        self.assertIsNone(context["site"])


class SiteProcessorTests(TenantSchemaTestCase):
    """Tests for the :func:`site_processor` context processor."""

    def setUp(self) -> None:
        super().setUp()
        self.request = RequestFactory().get("/")

    def test_returns_current_site(self) -> None:
        """The processor exposes the schema's current Site under ``site``."""
        context = site_processor(self.request)
        self.assertIn("site", context)
        self.assertIsInstance(context["site"], Site)
        self.assertEqual(context["site"].pk, 1)
