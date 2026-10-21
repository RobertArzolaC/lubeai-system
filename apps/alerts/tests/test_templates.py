"""Rendering tests for the real alerts templates."""

import shutil
import tempfile

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.alerts import factories
from apps.alerts.tests.base import AlertTenantTestCase
from apps.users.factories import UserFactory

DETAIL_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-alert-template-attachments-")


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given alerts permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="alerts",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)


@override_settings(MEDIA_ROOT=DETAIL_MEDIA_ROOT)
class AlertsTemplateRenderingTests(AlertTenantTestCase):
    """Render the real alerts templates to catch syntax and wiring errors."""

    @classmethod
    def setUpClass(cls) -> None:
        """Keep uploaded files out of the repository's media directory."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, DETAIL_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.alert = factories.AlertFactory()

    def test_list_template_renders(self) -> None:
        """The alert list template renders successfully."""
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "alerts/alert/list.html")

    def test_list_template_drops_parameter_column(self) -> None:
        """The list no longer renders the removed parameter concept."""
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertNotContains(response, "Parameter")
        self.assertContains(response, self.alert.get_category_display())

    def test_list_template_exposes_the_status_modal(self) -> None:
        """The list offers the status modal next to the row actions."""
        response = self.client.get(reverse("apps.alerts:alert_list"))
        status_url = reverse(
            "apps.alerts:alert_status_update", kwargs={"pk": self.alert.pk}
        )
        self.assertContains(response, 'class="js-status')
        self.assertContains(response, f'data-url="{status_url}"')

    def test_status_modal_collects_note_and_attachment(self) -> None:
        """The status modal exposes the description and optional file inputs."""
        response = self.client.get(reverse("apps.alerts:alert_list"))

        self.assertContains(response, 'id="alert-status-modal-template"')
        self.assertContains(response, 'id="alert-status-value"')
        self.assertContains(response, 'id="alert-status-note"')
        self.assertContains(response, 'id="alert-status-attachment"')
        self.assertContains(response, 'id="alert-status-help"')
        self.assertContains(response, 'accept=".pdf,.png,.jpg,.jpeg,.webp"')
        self.assertContains(response, 'maxlength="1000"')
        self.assertContains(response, "FormData")
        self.assertContains(response, "payload.errors")
        self.assertContains(
            response,
            "const modalTemplate = document.getElementById('alert-status-modal-template');",
        )
        self.assertContains(response, "html: modalTemplate.innerHTML")

    def test_list_avoids_n_plus_one_queries(self) -> None:
        """The list query count does not grow with the number of alerts."""
        # Warm up one-time writes (constance persists defaults on first read,
        # and the current site is resolved once) so the comparison measures the
        # list query itself rather than first-request setup.
        self.client.get(reverse("apps.alerts:alert_list"))
        with CaptureQueriesContext(connection) as few:
            self.client.get(reverse("apps.alerts:alert_list"))
        factories.AlertFactory.create_batch(5)
        with CaptureQueriesContext(connection) as many:
            self.client.get(reverse("apps.alerts:alert_list"))
        self.assertEqual(len(few.captured_queries), len(many.captured_queries))

    def test_detail_template_renders(self) -> None:
        """The alert detail template renders successfully."""
        response = self.client.get(
            reverse("apps.alerts:alert_detail", kwargs={"pk": self.alert.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "alerts/alert/detail.html")

    def test_detail_renders_the_status_history(self) -> None:
        """The detail shows the note and a link to the attachment."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert,
            previous_status="OPEN",
            status="RESOLVED",
            note="Se reemplazó el filtro y se recargó el aceite.",
            attachment=SimpleUploadedFile(
                "evidencia.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
        )

        response = self.client.get(
            reverse("apps.alerts:alert_detail", kwargs={"pk": self.alert.pk})
        )

        self.assertContains(response, "Se reemplazó el filtro y se recargó el aceite.")
        self.assertContains(
            response,
            reverse("apps.alerts:alert_attachment_download", kwargs={"pk": entry.pk}),
        )
        self.assertContains(response, entry.attachment_filename)

    def test_list_hides_the_status_modal_without_change_permission(self) -> None:
        """Users who can only view alerts do not receive the modal markup."""
        user = UserFactory()
        grant_permissions(user, "view_alert")
        self.client.force_login(user)

        response = self.client.get(reverse("apps.alerts:alert_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "js-status")
        self.assertNotContains(response, 'id="alert-status-modal-template"')

    def test_detail_escapes_the_status_note(self) -> None:
        """A note with HTML is rendered escaped in the timeline."""
        factories.AlertStatusHistoryFactory(
            alert=self.alert,
            note="<script>alert(1)</script>",
        )

        response = self.client.get(
            reverse("apps.alerts:alert_detail", kwargs={"pk": self.alert.pk})
        )

        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_detail_query_count_is_stable_with_history(self) -> None:
        """The detail query count does not grow with the history entries."""
        detail_url = reverse("apps.alerts:alert_detail", kwargs={"pk": self.alert.pk})
        self.client.get(detail_url)
        with CaptureQueriesContext(connection) as few:
            self.client.get(detail_url)
        factories.AlertStatusHistoryFactory.create_batch(5, alert=self.alert)
        with CaptureQueriesContext(connection) as many:
            self.client.get(detail_url)
        self.assertEqual(len(few.captured_queries), len(many.captured_queries))

    def test_form_template_renders(self) -> None:
        """The alert edit form template renders successfully."""
        response = self.client.get(
            reverse("apps.alerts:alert_update", kwargs={"pk": self.alert.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "alerts/alert/form.html")
