"""Tests for the ``apps.alerts.models`` module."""

import shutil
import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from apps.alerts import factories, models, validators
from apps.alerts.tests.base import AlertTenantTestCase
from apps.users import factories as user_factories

MODEL_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-alert-model-attachments-")


@override_settings(MEDIA_ROOT=MODEL_MEDIA_ROOT)
class AlertStatusHistoryModelTests(AlertTenantTestCase):
    """Tests for the status history attached to an alert."""

    @classmethod
    def setUpClass(cls) -> None:
        """Keep uploaded files out of the repository's media directory."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, MODEL_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        """Build one alert and the acting user."""
        super().setUp()
        self.user = user_factories.UserFactory()
        self.alert = factories.AlertFactory(status="OPEN")

    def test_history_orders_newest_first(self) -> None:
        """The related manager returns the latest change first."""
        first = factories.AlertStatusHistoryFactory(alert=self.alert, note="first")
        models.AlertStatusHistory.objects.filter(pk=first.pk).update(
            created=timezone.now() - timedelta(hours=1)
        )
        second = factories.AlertStatusHistoryFactory(alert=self.alert, note="second")

        self.assertEqual(list(self.alert.status_history.all()), [second, first])

    def test_upload_path_uses_organization_and_uuid(self) -> None:
        """The stored path is non-guessable and grouped by organization."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert,
            attachment=SimpleUploadedFile(
                "evidence.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
        )

        self.assertTrue(
            entry.attachment.name.startswith(
                f"alerts/attachments/{self.alert.organization_id}/"
            )
        )
        self.assertRegex(entry.attachment.name, r"/[0-9a-f]{32}\.pdf$")

    def test_status_labels_fall_back_to_raw_value(self) -> None:
        """Known statuses are translated; unknown values are returned as-is."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert,
            previous_status="OPEN",
            status="RESOLVED",
        )

        self.assertEqual(entry.previous_status_label, "Abierta")
        self.assertEqual(entry.status_label, "Resuelta")

        entry.status = "UNKNOWN"
        self.assertEqual(entry.status_label, "UNKNOWN")

    def test_create_status_change_links_the_alert(self) -> None:
        """The inherited helper records the alert, actor and previous status."""
        entry = models.AlertStatusHistory.create_status_change(
            self.alert,
            "ACKNOWLEDGED",
            self.user,
            note="Reviewed with the client",
        )

        self.assertEqual(entry.alert, self.alert)
        self.assertEqual(entry.previous_status, "OPEN")
        self.assertEqual(entry.status, "ACKNOWLEDGED")
        self.assertEqual(entry.note, "Reviewed with the client")
        self.assertEqual(entry.created_by, self.user)
        self.assertEqual(entry.updated_by, self.user)

    def test_attachment_filename_returns_only_the_name(self) -> None:
        """The template helper hides the storage path."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert,
            attachment=SimpleUploadedFile(
                "evidence.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
        )

        self.assertNotIn("/", entry.attachment_filename)
        self.assertTrue(entry.attachment_filename.endswith(".pdf"))

    def test_attachment_filename_prefers_the_original_name(self) -> None:
        """The name typed by the user is shown instead of the UUID path."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert,
            original_filename="evidencia.pdf",
            attachment=SimpleUploadedFile(
                "evidence.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
        )

        self.assertEqual(entry.attachment_filename, "evidencia.pdf")


class AlertAttachmentValidatorTests(AlertTenantTestCase):
    """Validation rules for the optional status attachment."""

    def test_validator_rejects_a_disallowed_extension(self) -> None:
        """Only PDF and image extensions are accepted."""
        file = SimpleUploadedFile("evidence.exe", b"MZ")

        with self.assertRaises(ValidationError):
            validators.validate_alert_attachment(file)

    def test_validator_rejects_a_fake_pdf(self) -> None:
        """A file named ``.pdf`` must still carry the PDF signature."""
        file = SimpleUploadedFile("evidence.pdf", b"not a pdf")

        with self.assertRaises(ValidationError):
            validators.validate_alert_attachment(file)

    def test_validator_accepts_a_real_pdf(self) -> None:
        """A real PDF header passes validation."""
        file = SimpleUploadedFile(
            "evidence.pdf", b"%PDF-1.4 test", content_type="application/pdf"
        )

        validators.validate_alert_attachment(file)

    def test_validator_rejects_an_oversized_attachment(self) -> None:
        """Files above the configured limit are rejected."""
        file = SimpleUploadedFile(
            "evidence.pdf",
            b"%PDF-" + b"0" * validators.MAX_ALERT_ATTACHMENT_SIZE,
            content_type="application/pdf",
        )

        with self.assertRaises(ValidationError):
            validators.validate_alert_attachment(file)
