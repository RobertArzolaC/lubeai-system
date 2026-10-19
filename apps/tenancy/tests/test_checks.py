"""Tests for the tenancy system checks.

The checks turn a legacy database — business tables stranded in the ``public``
schema — into a loud failure in production and a warning in development. A
clean database must stay quiet so the checks never block the normal flow.
"""

from __future__ import annotations

from django.db import connection
from django.test import TestCase, override_settings

from apps.tenancy import checks


class LegacyPublicTablesCheckTests(TestCase):
    """Detection of business tables that stayed in ``public``."""

    #: Table created by the tests to simulate a pre-split database. It matches
    #: one of :data:`apps.tenancy.checks.LEGACY_PUBLIC_TABLES`.
    LEGACY_TABLE = "organizations_organization"

    def create_legacy_table(self) -> None:
        """Create a business table inside ``public`` as a legacy database would.

        ``CREATE TABLE`` is transactional in PostgreSQL, so the extra table is
        rolled back with the test's transaction and cannot leak to another test.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE public.{self.LEGACY_TABLE} (id serial PRIMARY KEY)"
            )

    def test_clean_database_reports_nothing(self) -> None:
        """A schema-split database has no business tables in ``public``."""
        self.assertEqual(checks.check_legacy_public_tables(), [])

    @override_settings(DEBUG=False)
    def test_legacy_table_is_an_error_in_production(self) -> None:
        """With ``DEBUG=False`` the stranded data aborts loudly."""
        self.create_legacy_table()

        issues = checks.check_legacy_public_tables()

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, "tenancy.E001")
        self.assertIn(self.LEGACY_TABLE, issues[0].msg)
        self.assertIn("docs/despliegue-multi-tenant.md", issues[0].hint)

    @override_settings(DEBUG=True)
    def test_legacy_table_is_a_warning_in_development(self) -> None:
        """With ``DEBUG=True`` the same state only warns."""
        self.create_legacy_table()

        issues = checks.check_legacy_public_tables()

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, "tenancy.W001")
