"""Rendering tests for the real alerts templates."""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.alerts import factories
from apps.users.factories import UserFactory


class AlertsTemplateRenderingTests(TestCase):
    """Render the real alerts templates to catch syntax and wiring errors."""

    def setUp(self) -> None:
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.alert = factories.AlertFactory()

    def test_list_template_renders(self) -> None:
        """The alert list template renders successfully."""
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "alerts/alert/list.html")

    def test_list_avoids_n_plus_one_queries(self) -> None:
        """The list query count does not grow with the number of alerts."""
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
