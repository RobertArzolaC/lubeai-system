"""Rendering tests for the real reports templates."""

from django.test import TestCase
from django.urls import reverse

from apps.reports import factories
from apps.users.factories import UserFactory


class ReportsTemplateRenderingTests(TestCase):
    """Render the real reports templates to catch syntax and wiring errors."""

    def setUp(self) -> None:
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.laboratory = factories.LaboratoryFactory()
        self.report = factories.ReportFactory()
        factories.LabAnalysisFactory(report=self.report)
        self.threshold = factories.AnalysisThresholdFactory()

    def test_list_templates_render(self) -> None:
        """Every reports list template renders successfully."""
        for name in (
            "laboratory_list",
            "report_list",
            "analysisthreshold_list",
        ):
            with self.subTest(view=name):
                response = self.client.get(reverse(f"apps.reports:{name}"))
                self.assertEqual(response.status_code, 200)

    def test_detail_templates_render(self) -> None:
        """Every reports detail template renders successfully."""
        cases = {
            "laboratory_detail": self.laboratory.pk,
            "report_detail": self.report.pk,
            "analysisthreshold_detail": self.threshold.pk,
        }
        for name, pk in cases.items():
            with self.subTest(view=name):
                response = self.client.get(
                    reverse(f"apps.reports:{name}", kwargs={"pk": pk})
                )
                self.assertEqual(response.status_code, 200)

    def test_form_templates_render(self) -> None:
        """Every reports create form template renders successfully."""
        for name in (
            "laboratory_create",
            "report_create",
            "analysisthreshold_create",
        ):
            with self.subTest(view=name):
                response = self.client.get(reverse(f"apps.reports:{name}"))
                self.assertEqual(response.status_code, 200)

    def test_export_page_renders(self) -> None:
        """The export page renders successfully for authorized users."""
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertEqual(response.status_code, 200)
