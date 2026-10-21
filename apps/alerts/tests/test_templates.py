"""Rendering tests for the real alerts templates."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.alerts import factories
from apps.alerts.tests.base import AlertTenantTestCase
from apps.users.factories import UserFactory


class AlertsTemplateRenderingTests(AlertTenantTestCase):
    """Render the real alerts templates to catch syntax and wiring errors."""

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

        self.assertContains(response, 'id="alert-status-value"')
        self.assertContains(response, 'id="alert-status-note"')
        self.assertContains(response, 'id="alert-status-attachment"')
        self.assertContains(response, 'accept=".pdf,.png,.jpg,.jpeg,.webp"')
        self.assertContains(response, "FormData")

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

    def test_form_template_renders(self) -> None:
        """The alert edit form template renders successfully."""
        response = self.client.get(
            reverse("apps.alerts:alert_update", kwargs={"pk": self.alert.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "alerts/alert/form.html")
