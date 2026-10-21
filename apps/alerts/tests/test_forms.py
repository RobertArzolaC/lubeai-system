"""Tests for the ``apps.alerts.forms`` module."""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.alerts import factories, forms, validators
from apps.alerts.tests.base import AlertTenantTestCase
from apps.equipment import factories as equipment_factories
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.reports import factories as report_factories
from apps.users import factories as user_factories


def alert_payload(alert, **overrides: object) -> dict:
    """Build a valid AlertForm payload from an existing alert."""
    data: dict = {
        "machine": alert.machine_id,
        "component": alert.component_id,
        "report": alert.report_id,
        "category": alert.category,
        "severity": alert.severity,
        "status": alert.status,
        "value": alert.value,
        "warning_limit": alert.warning_limit,
        "critical_limit": alert.critical_limit,
        "unit": alert.unit,
        "detected_at": alert.detected_at,
    }
    data.update(overrides)
    return data


class AlertFormScopingTests(AlertTenantTestCase):
    """Alert relation choices stay inside the actor's organization tree."""

    def setUp(self) -> None:
        """Build one visible organization and one unrelated tenant."""
        super().setUp()
        self.org = organization_factories.OrganizationFactory(
            slug="alert-form-own", kind=choices.OrganizationKind.FINAL
        )
        self.other = organization_factories.OrganizationFactory(
            slug="alert-form-other", kind=choices.OrganizationKind.FINAL
        )
        self.user = user_factories.UserFactory()
        self.user.organization = self.org
        self.user.save(update_fields=["organization"])
        foreign_machine = equipment_factories.MachineFactory(organization=self.other)
        foreign_component = equipment_factories.ComponentFactory(
            machine=foreign_machine
        )
        self.foreign_report = report_factories.ReportFactory(
            machine=foreign_machine, component=foreign_component
        )

    def test_report_choices_exclude_other_organizations(self) -> None:
        """The report dropdown does not expose reports from other tenants."""
        form = forms.AlertForm(user=self.user)
        self.assertNotIn(self.foreign_report, form.fields["report"].queryset)


class AlertFormTests(AlertTenantTestCase):
    """Tests for :class:`AlertForm`."""

    def setUp(self) -> None:
        super().setUp()
        self.user = user_factories.UserFactory()
        self.alert = factories.AlertFactory(status="OPEN")

    def test_system_fields_are_not_editable(self) -> None:
        """System-managed fields are excluded from the form."""
        form = forms.AlertForm(instance=self.alert)
        for field in (
            "dedup_key",
            "parameter",
            "rule_type",
            "sent_channels",
            "created_by",
            "acknowledged_by",
        ):
            with self.subTest(field=field):
                self.assertNotIn(field, form.fields)

    def test_relation_querysets_limited_to_active(self) -> None:
        """Relation fields only offer active records."""
        inactive_machine = equipment_factories.MachineFactory(is_active=False)
        form = forms.AlertForm(instance=self.alert)
        self.assertNotIn(inactive_machine, form.fields["machine"].queryset)

    def test_equal_limits_are_invalid(self) -> None:
        """Warning and critical limits must be different."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, warning_limit=50, critical_limit=50),
            instance=self.alert,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("critical_limit", form.errors)

    def test_valid_form_saves_changes(self) -> None:
        """A valid payload updates the alert fields."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, severity="CRITICAL", value=123.0),
            instance=self.alert,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.severity, "CRITICAL")
        self.assertEqual(self.alert.value, 123.0)

    def test_save_applies_acknowledgement_transition(self) -> None:
        """Saving with ACKNOWLEDGED stamps the author and timestamp."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, status="ACKNOWLEDGED"),
            instance=self.alert,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.acknowledged_by, self.user)
        self.assertIsNotNone(self.alert.acknowledged_at)
        history = self.alert.status_history.get()
        self.assertEqual(history.previous_status, "OPEN")
        self.assertEqual(history.status, "ACKNOWLEDGED")
        self.assertEqual(history.note, "")
        self.assertEqual(history.created_by, self.user)

    def test_save_applies_resolution_transition(self) -> None:
        """Saving with RESOLVED stamps the resolution timestamp."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, status="RESOLVED"),
            instance=self.alert,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.alert.refresh_from_db()
        self.assertIsNotNone(self.alert.resolved_at)
        self.assertEqual(self.alert.status_history.get().status, "RESOLVED")

    def test_save_without_status_change_does_not_record_history(self) -> None:
        """Editing other fields does not create audit noise."""
        form = forms.AlertForm(
            data=alert_payload(self.alert, value=91.0),
            instance=self.alert,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.value, 91.0)
        self.assertFalse(self.alert.status_history.exists())


FORM_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-alert-form-attachments-")


@override_settings(MEDIA_ROOT=FORM_MEDIA_ROOT)
class AlertStatusFormTests(AlertTenantTestCase):
    """Validation rules for the status modal form."""

    @classmethod
    def setUpClass(cls) -> None:
        """Keep uploaded files out of the repository's media directory."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, FORM_MEDIA_ROOT, ignore_errors=True)

    def test_note_and_attachment_are_optional(self) -> None:
        """A status change can be submitted without note or file."""
        form = forms.AlertStatusForm(data={"status": "RESOLVED"})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["note"], "")
        self.assertIsNone(form.cleaned_data["attachment"])

    def test_rejects_an_attachment_over_ten_megabytes(self) -> None:
        """The configured size limit is enforced by the form."""
        file = SimpleUploadedFile(
            "evidence.pdf",
            b"%PDF-" + b"0" * validators.MAX_ALERT_ATTACHMENT_SIZE,
            content_type="application/pdf",
        )

        form = forms.AlertStatusForm(
            data={"status": "RESOLVED"},
            files={"attachment": file},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_rejects_a_disallowed_extension(self) -> None:
        """Executable files cannot be attached to a status change."""
        file = SimpleUploadedFile("evidence.exe", b"MZ")

        form = forms.AlertStatusForm(
            data={"status": "RESOLVED"},
            files={"attachment": file},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_rejects_a_fake_pdf(self) -> None:
        """A .pdf extension without the PDF signature is rejected."""
        file = SimpleUploadedFile("evidence.pdf", b"not a pdf")

        form = forms.AlertStatusForm(
            data={"status": "RESOLVED"},
            files={"attachment": file},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_accepts_pdf_and_image_signatures(self) -> None:
        """PDF, PNG, JPEG and WEBP files pass validation."""
        samples = {
            "evidence.pdf": b"%PDF-1.4 test",
            "evidence.png": b"\x89PNG\r\n\x1a\n" + b"0" * 8,
            "evidence.jpg": b"\xff\xd8\xff" + b"0" * 8,
            "evidence.webp": b"RIFF0000WEBP" + b"0" * 8,
        }

        for filename, content in samples.items():
            with self.subTest(filename=filename):
                form = forms.AlertStatusForm(
                    data={"status": "RESOLVED"},
                    files={"attachment": SimpleUploadedFile(filename, content)},
                )
                self.assertTrue(form.is_valid(), form.errors)
