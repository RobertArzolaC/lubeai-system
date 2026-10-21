"""Tests for the reports admin PDF integration."""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.core.tests.base import TenantSchemaTestCase
from apps.reports import admin, factories, widgets
from apps.users import factories as user_factories

ADMIN_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-report-admin-pdf-")


@override_settings(MEDIA_ROOT=ADMIN_MEDIA_ROOT)
class ReportAdminPDFTests(TenantSchemaTestCase):
    """The report admin uploads PDFs without leaking direct media URLs."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create the temporary media root used by the file field."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, ADMIN_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        """Log in a superuser and create a report with a PDF."""
        super().setUp()
        self.user = user_factories.UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.report = factories.ReportFactory(
            pdf_file=SimpleUploadedFile(
                "report.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            )
        )

    def test_admin_form_uses_safe_pdf_widget(self) -> None:
        """The admin form uses the widget that hides MEDIA_URL."""
        form = admin.ReportAdminForm()
        self.assertIsInstance(form.fields["pdf_file"].widget, widgets.ReportPDFInput)

    def test_change_page_links_to_the_download_view(self) -> None:
        """The change page links to the scoped download view, not to media."""
        response = self.client.get(
            reverse("admin:reports_report_change", args=[self.report.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("apps.reports:report_pdf_download", args=[self.report.pk]),
        )
        self.assertNotContains(response, self.report.pdf_file.url)
