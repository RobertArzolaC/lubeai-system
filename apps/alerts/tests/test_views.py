"""Tests for the ``apps.alerts.views`` module."""

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.alerts import factories, models
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
        "parameter": alert.parameter,
        "category": alert.category,
        "severity": alert.severity,
        "status": alert.status,
        "value": alert.value,
        "warning_limit": alert.warning_limit,
        "critical_limit": alert.critical_limit,
        "unit": alert.unit,
        "rule_type": alert.rule_type,
        "detected_at": alert.detected_at,
    }
    data.update(overrides)
    return data


@override_settings(TEMPLATES=ALERTS_TEMPLATES)
class AlertViewTests(TestCase):
    """CRUD tests for the Alert views."""

    def setUp(self) -> None:
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
