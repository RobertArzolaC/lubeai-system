"""Tests for the dummy report PDF backfill command."""

import shutil
import tempfile
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django_tenants.management.commands import BaseTenantCommand

from apps.core.tests.base import TenantSchemaTestCase
from apps.reports import factories
from apps.reports.management.commands.add_dummy_report_pdfs import (
    Command as BackfillCommand,
)

COMMAND_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-report-command-pdf-")


def stored_pdf() -> SimpleUploadedFile:
    """Return a minimal stored PDF."""
    return SimpleUploadedFile(
        "report.pdf", b"%PDF-1.4 test", content_type="application/pdf"
    )


class DummyPDFCommandWiringTests(SimpleTestCase):
    """The public command is a multi-tenant wrapper."""

    def test_wrapper_uses_the_tenant_command(self) -> None:
        """The wrapper delegates to the per-schema command."""
        self.assertTrue(issubclass(BackfillCommand, BaseTenantCommand))
        self.assertEqual(BackfillCommand.COMMAND_NAME, "add_dummy_report_pdfs_tenant")

    def test_wrapper_skips_public_by_default(self) -> None:
        """The public schema has no reports table and is skipped by default."""
        parser = BackfillCommand().create_parser("manage.py", "add_dummy_report_pdfs")
        self.assertTrue(parser.parse_args([]).skip_public)

    def test_execute_command_drops_wrapper_only_options(self) -> None:
        """Only the options declared by the wrapped command are forwarded."""
        command = BackfillCommand()
        tenant = SimpleNamespace(schema_name="acme")
        with mock.patch.object(BaseTenantCommand, "execute_command") as parent:
            command.execute_command(
                tenant,
                "add_dummy_report_pdfs_tenant",
                overwrite=True,
                limit=1,
                dry_run=True,
                schema_name="acme",
                skip_public=True,
            )
        parent.assert_called_once_with(
            tenant,
            "add_dummy_report_pdfs_tenant",
            overwrite=True,
            limit=1,
            dry_run=True,
        )


@override_settings(MEDIA_ROOT=COMMAND_MEDIA_ROOT)
class DummyPDFBackfillCommandTests(TenantSchemaTestCase):
    """The per-schema command fills only the reports missing a PDF."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create the temporary media root used by the file field."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, COMMAND_MEDIA_ROOT, ignore_errors=True)

    def run_command(self, **options: object) -> str:
        """Run the tenant command and return its output."""
        output = StringIO()
        call_command("add_dummy_report_pdfs_tenant", stdout=output, **options)
        return output.getvalue()

    def test_command_creates_pdf_for_reports_without_one(self) -> None:
        """Reports without a PDF receive a generated document."""
        first = factories.ReportFactory()
        second = factories.ReportFactory()

        output = self.run_command()

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.pdf_file)
        self.assertTrue(second.pdf_file)
        self.assertEqual(
            first.pdf_file.storage.open(first.pdf_file.name).read(5), b"%PDF-"
        )
        self.assertIn("2 reports", output)

    def test_command_skips_reports_with_pdf(self) -> None:
        """Existing PDFs are preserved unless overwrite is requested."""
        report = factories.ReportFactory(pdf_file=stored_pdf())
        original_name = report.pdf_file.name

        self.run_command()
        report.refresh_from_db()

        self.assertEqual(report.pdf_file.name, original_name)

    def test_command_overwrite_replaces_pdf_and_deletes_old_file(self) -> None:
        """Overwrite replaces the stored document and cleans the previous file."""
        report = factories.ReportFactory(pdf_file=stored_pdf())
        storage = report.pdf_file.storage
        original_name = report.pdf_file.name

        with self.captureOnCommitCallbacks(execute=True):
            self.run_command(overwrite=True)
        report.refresh_from_db()

        self.assertNotEqual(report.pdf_file.name, original_name)
        self.assertFalse(storage.exists(original_name))
        self.assertTrue(storage.exists(report.pdf_file.name))

    def test_command_is_idempotent(self) -> None:
        """A second run does not change the generated file."""
        report = factories.ReportFactory()
        self.run_command()
        report.refresh_from_db()
        first_name = report.pdf_file.name

        output = self.run_command()
        report.refresh_from_db()

        self.assertEqual(report.pdf_file.name, first_name)
        self.assertIn("0 reports", output)

    def test_command_respects_limit(self) -> None:
        """The limit option processes only the requested number of reports."""
        reports = factories.ReportFactory.create_batch(3)

        self.run_command(limit=1)

        for report in reports:
            report.refresh_from_db()
        self.assertEqual(sum(1 for report in reports if report.pdf_file), 1)

    def test_dry_run_does_not_write_files(self) -> None:
        """The dry run reports the candidates without storing anything."""
        report = factories.ReportFactory()

        output = self.run_command(dry_run=True)
        report.refresh_from_db()

        self.assertFalse(report.pdf_file)
        self.assertIn("1 reports would be updated", output)
