"""Tests for report PDF file lifecycle signals."""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.core.tests.base import TenantSchemaTestCase
from apps.reports import factories

SIGNAL_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-report-signal-pdf-")


def pdf_file(name: str = "report.pdf") -> SimpleUploadedFile:
    """Return a minimal uploaded PDF."""
    return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")


@override_settings(MEDIA_ROOT=SIGNAL_MEDIA_ROOT)
class ReportPDFSignalTests(TenantSchemaTestCase):
    """Replacing or deleting a report also cleans up its stored PDF."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create the temporary media root used by the file field."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, SIGNAL_MEDIA_ROOT, ignore_errors=True)

    def test_replacing_pdf_deletes_the_previous_file(self) -> None:
        """Saving a new PDF removes the old file from storage."""
        report = factories.ReportFactory(pdf_file=pdf_file())
        storage = report.pdf_file.storage
        old_name = report.pdf_file.name

        report.pdf_file = pdf_file("replacement.pdf")
        report.save()

        self.assertFalse(storage.exists(old_name))
        self.assertTrue(storage.exists(report.pdf_file.name))

    def test_deleting_report_deletes_the_pdf(self) -> None:
        """Deleting a report removes its stored PDF."""
        report = factories.ReportFactory(pdf_file=pdf_file())
        storage = report.pdf_file.storage
        stored_name = report.pdf_file.name

        report.delete()

        self.assertFalse(storage.exists(stored_name))
