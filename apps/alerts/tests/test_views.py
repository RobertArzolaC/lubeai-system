"""Tests for the ``apps.alerts.views`` module."""

import shutil
import tempfile

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import NoReverseMatch, reverse

from apps.alerts import factories, models
from apps.alerts.tests.base import AlertTenantTestCase
from apps.organizations import factories as organization_factories
from apps.users import factories as users_factories

ALERTS_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [settings.BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "alerts/alert/list.html": "",
                        "alerts/alert/detail.html": "",
                        "alerts/alert/form.html": "",
                    },
                ),
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "constance.context_processors.config",
                "apps.core.context_processors.site_processor",
            ],
        },
    }
]


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given alerts permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="alerts",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)


def alert_payload(alert, **overrides: object) -> dict:
    """Build a valid alert form payload."""
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


@override_settings(TEMPLATES=ALERTS_TEMPLATES)
class AlertViewTests(AlertTenantTestCase):
    """CRUD tests for the Alert views."""

    def setUp(self) -> None:
        super().setUp()
        self.user = users_factories.UserFactory()
        self.alert = factories.AlertFactory(status="OPEN", severity="CRITICAL")

    def test_list_requires_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertEqual(response.status_code, 302)

    def test_list_requires_permission(self) -> None:
        """Authenticated users without permission get a 403."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertEqual(response.status_code, 403)

    def test_list_renders_with_permission(self) -> None:
        """Authorized users can list alerts."""
        grant_permissions(self.user, "view_alert")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "alerts/alert/list.html")
        self.assertIn(self.alert, response.context["alerts"])

    def test_list_filters_by_status(self) -> None:
        """The list applies the status filter."""
        other = factories.AlertFactory(status="RESOLVED")
        grant_permissions(self.user, "view_alert")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.alerts:alert_list"), {"status": "RESOLVED"}
        )
        self.assertIn(other, response.context["alerts"])
        self.assertNotIn(self.alert, response.context["alerts"])

    def test_list_uses_items_per_page(self) -> None:
        """A valid ``items_per_page`` overrides the page size."""
        grant_permissions(self.user, "view_alert")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.alerts:alert_list"), {"items_per_page": "5"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].per_page, 5)

    def test_list_ignores_invalid_items_per_page(self) -> None:
        """An invalid ``items_per_page`` falls back to the default page size."""
        grant_permissions(self.user, "view_alert")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.alerts:alert_list"), {"items_per_page": "999"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].per_page, 5)

    def test_detail_renders(self) -> None:
        """Authorized users can open the alert detail."""
        grant_permissions(self.user, "view_alert")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.alerts:alert_detail", kwargs={"pk": self.alert.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["alert"], self.alert)

    def test_update_post_updates_alert(self) -> None:
        """A valid post updates the alert."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.alerts:alert_update", kwargs={"pk": self.alert.pk}),
            alert_payload(self.alert, severity="WARNING", value=77.0),
        )
        self.assertRedirects(
            response,
            reverse("apps.alerts:alert_list"),
            fetch_redirect_response=False,
        )
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.severity, "WARNING")
        self.assertEqual(self.alert.value, 77.0)

    def test_update_applies_status_transition(self) -> None:
        """Acknowledging through the edit form stamps the author."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)
        self.client.post(
            reverse("apps.alerts:alert_update", kwargs={"pk": self.alert.pk}),
            alert_payload(self.alert, status="ACKNOWLEDGED"),
        )
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.acknowledged_by, self.user)
        self.assertIsNotNone(self.alert.acknowledged_at)

    def test_delete_requires_permission(self) -> None:
        """Deleting without permission returns a JSON 403."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.alerts:alert_delete", kwargs={"pk": self.alert.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "error")

    def test_delete_success(self) -> None:
        """Authorized users can delete an alert."""
        grant_permissions(self.user, "delete_alert")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.alerts:alert_delete", kwargs={"pk": self.alert.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertFalse(models.Alert.objects.filter(pk=self.alert.pk).exists())

    def test_create_url_removed(self) -> None:
        """Alerts cannot be created manually, so no create URL exists."""
        with self.assertRaises(NoReverseMatch):
            reverse("apps.alerts:alert_create")


class AlertStatusUpdateViewTests(AlertTenantTestCase):
    """The status modal updates only the lifecycle status of an alert."""

    def setUp(self) -> None:
        super().setUp()
        self.user = users_factories.UserFactory()
        self.alert = factories.AlertFactory(
            status="OPEN",
            severity="CRITICAL",
            value=88.0,
            unit="ppm",
        )

    def _url(self) -> str:
        return reverse(
            "apps.alerts:alert_status_update", kwargs={"pk": self.alert.pk}
        )

    def test_status_update_requires_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.post(self._url(), {"status": "ACKNOWLEDGED"})
        self.assertEqual(response.status_code, 302)

    def test_status_update_requires_permission(self) -> None:
        """Authenticated users without permission get a JSON 403."""
        self.client.force_login(self.user)
        response = self.client.post(self._url(), {"status": "ACKNOWLEDGED"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "error")

    def test_status_update_rejects_an_invalid_status(self) -> None:
        """A value outside the enumeration is rejected with a JSON 400."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)
        response = self.client.post(self._url(), {"status": "NOPE"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "OPEN")

    def test_status_update_acknowledges_the_alert(self) -> None:
        """Acknowledging stamps the actor and the timestamp."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)
        response = self.client.post(self._url(), {"status": "ACKNOWLEDGED"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["new_status"], "ACKNOWLEDGED")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "ACKNOWLEDGED")
        self.assertEqual(self.alert.acknowledged_by, self.user)
        self.assertIsNotNone(self.alert.acknowledged_at)

    def test_status_update_touches_nothing_else(self) -> None:
        """The endpoint only changes the status and its lifecycle stamps."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)
        self.client.post(self._url(), {"status": "RESOLVED"})

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.severity, "CRITICAL")
        self.assertEqual(self.alert.value, 88.0)
        self.assertEqual(self.alert.unit, "ppm")
        self.assertIsNotNone(self.alert.resolved_at)

    def test_status_update_reopens_the_alert(self) -> None:
        """Going back to open clears the acknowledgement fields."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)
        self.client.post(self._url(), {"status": "ACKNOWLEDGED"})

        self.client.post(self._url(), {"status": "OPEN"})

        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "OPEN")
        self.assertIsNone(self.alert.acknowledged_at)
        self.assertIsNone(self.alert.acknowledged_by_id)
        self.assertIsNone(self.alert.resolved_at)

    def test_status_update_persists_the_note(self) -> None:
        """The description submitted by the modal is stored in the history."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)

        response = self.client.post(
            self._url(),
            {"status": "RESOLVED", "note": "Se reemplazó el filtro"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["new_status"], "RESOLVED")
        history = self.alert.status_history.get()
        self.assertEqual(history.previous_status, "OPEN")
        self.assertEqual(history.note, "Se reemplazó el filtro")
        self.assertEqual(history.created_by, self.user)
        self.assertEqual(payload["history_id"], history.pk)

    def test_status_update_rejects_a_note_over_the_limit(self) -> None:
        """A description longer than 1000 characters is rejected."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)

        response = self.client.post(
            self._url(),
            {"status": "RESOLVED", "note": "x" * 1001},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "OPEN")
        self.assertFalse(self.alert.status_history.exists())

    def test_status_update_is_get_forbidden(self) -> None:
        """The endpoint accepts POST only."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 405)

    def test_status_update_scopes_to_the_visible_organizations(self) -> None:
        """An alert of an organization outside the user's subtree is a 404."""
        home = organization_factories.OrganizationFactory(slug="casa")
        self.user.organization = home
        self.user.save(update_fields=["organization"])
        grant_permissions(self.user, "change_alert")
        foreign = organization_factories.OrganizationFactory(slug="ajena")
        hidden = factories.AlertFactory(status="OPEN", organization=foreign)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("apps.alerts:alert_status_update", kwargs={"pk": hidden.pk}),
            {"status": "RESOLVED"},
        )

        self.assertEqual(response.status_code, 404)
        hidden.refresh_from_db()
        self.assertEqual(hidden.status, "OPEN")


ATTACHMENT_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-alert-view-attachments-")


@override_settings(MEDIA_ROOT=ATTACHMENT_MEDIA_ROOT)
class AlertStatusAttachmentTests(AlertTenantTestCase):
    """Uploads and protected downloads for the status modal."""

    @classmethod
    def setUpClass(cls) -> None:
        """Keep uploaded files out of the repository's media directory."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, ATTACHMENT_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        super().setUp()
        self.user = users_factories.UserFactory()
        self.alert = factories.AlertFactory(status="OPEN")

    def _status_url(self) -> str:
        return reverse(
            "apps.alerts:alert_status_update", kwargs={"pk": self.alert.pk}
        )

    def _download_url(self, entry) -> str:
        return reverse(
            "apps.alerts:alert_attachment_download", kwargs={"pk": entry.pk}
        )

    def _pdf(self, filename: str = "evidence.pdf") -> SimpleUploadedFile:
        return SimpleUploadedFile(
            filename,
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )

    def test_status_update_stores_the_attachment(self) -> None:
        """The uploaded file is persisted and exposed through a scoped URL."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)

        response = self.client.post(
            self._status_url(),
            {"status": "RESOLVED", "attachment": self._pdf()},
        )

        self.assertEqual(response.status_code, 200)
        history = self.alert.status_history.get()
        self.assertTrue(history.attachment)
        self.assertTrue(history.attachment.storage.exists(history.attachment.name))
        self.assertEqual(
            response.json()["attachment_url"],
            self._download_url(history),
        )

    def test_status_update_rejects_an_invalid_attachment(self) -> None:
        """An executable file is rejected and nothing is persisted."""
        grant_permissions(self.user, "change_alert")
        self.client.force_login(self.user)

        response = self.client.post(
            self._status_url(),
            {
                "status": "RESOLVED",
                "attachment": SimpleUploadedFile("evidence.exe", b"MZ"),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "OPEN")
        self.assertFalse(self.alert.status_history.exists())

    def test_attachment_download_requires_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert, attachment=self._pdf()
        )

        response = self.client.get(self._download_url(entry))

        self.assertEqual(response.status_code, 302)

    def test_attachment_download_requires_permission(self) -> None:
        """Authenticated users without ``view_alert`` get a 403."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert, attachment=self._pdf()
        )
        self.client.force_login(self.user)

        response = self.client.get(self._download_url(entry))

        self.assertEqual(response.status_code, 403)

    def test_attachment_download_returns_an_attachment(self) -> None:
        """Authorized users receive the stored file as an attachment."""
        entry = factories.AlertStatusHistoryFactory(
            alert=self.alert, attachment=self._pdf()
        )
        grant_permissions(self.user, "view_alert")
        self.client.force_login(self.user)

        response = self.client.get(self._download_url(entry))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(
            b"".join(response.streaming_content),
            b"%PDF-1.4 test",
        )

    def test_attachment_download_scopes_to_visible_organizations(self) -> None:
        """An attachment of a foreign organization is a 404."""
        home = organization_factories.OrganizationFactory(slug="casa-adjuntos")
        self.user.organization = home
        self.user.save(update_fields=["organization"])
        grant_permissions(self.user, "view_alert")
        foreign = organization_factories.OrganizationFactory(slug="ajena-adjuntos")
        hidden_alert = factories.AlertFactory(status="OPEN", organization=foreign)
        entry = factories.AlertStatusHistoryFactory(
            alert=hidden_alert, attachment=self._pdf()
        )
        self.client.force_login(self.user)

        response = self.client.get(self._download_url(entry))

        self.assertEqual(response.status_code, 404)

    def test_attachment_download_without_file_is_404(self) -> None:
        """A history entry without an attachment cannot be downloaded."""
        entry = factories.AlertStatusHistoryFactory(alert=self.alert)
        grant_permissions(self.user, "view_alert")
        self.client.force_login(self.user)

        response = self.client.get(self._download_url(entry))

        self.assertEqual(response.status_code, 404)
