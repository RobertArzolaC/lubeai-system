"""Tests for the alerts admin status-history integration."""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.alerts import factories
from apps.alerts.tests.base import AlertTenantTestCase
from apps.users import factories as user_factories

ADMIN_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-alert-admin-attachments-")


@override_settings(MEDIA_ROOT=ADMIN_MEDIA_ROOT)
class AlertAdminAttachmentTests(AlertTenantTestCase):
    """The admin links attachments through the protected download view."""

    @classmethod
    def setUpClass(cls) -> None:
        """Keep uploaded files out of the repository's media directory."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, ADMIN_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        """Log in a superuser and create an alert with one history entry."""
        super().setUp()
        self.user = user_factories.UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.alert = factories.AlertFactory()
        self.entry = factories.AlertStatusHistoryFactory(
            alert=self.alert,
            original_filename="evidencia.pdf",
            attachment=SimpleUploadedFile(
                "evidencia.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
        )

    def test_change_page_links_to_the_download_view(self) -> None:
        """The alert change page uses the scoped view and shows the name."""
        response = self.client.get(
            reverse("admin:alerts_alert_change", args=[self.alert.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("apps.alerts:alert_attachment_download", args=[self.entry.pk]),
        )
        self.assertContains(response, "evidencia.pdf")
        self.assertNotContains(response, self.entry.attachment.url)
