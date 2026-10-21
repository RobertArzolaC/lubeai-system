"""Rendering tests for the real reports templates."""

import shutil
import tempfile
from pathlib import Path

from constance.test import override_config
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from apps.core.tests.base import TenantSchemaTestCase
from apps.reports import factories
from apps.users.factories import UserFactory

PDF_TEMPLATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-report-template-pdf-")


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given reports permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="reports", codename__in=codenames
    )
    user.user_permissions.add(*permissions)


class ReportsTemplateRenderingTests(TenantSchemaTestCase):
    """Render the real reports templates to catch syntax and wiring errors."""

    def setUp(self) -> None:
        super().setUp()
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

    def test_report_list_has_no_status_or_record_status_filter(self) -> None:
        """The real report list renders no status or record-status filters."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertNotContains(response, 'name="status"')
        self.assertNotContains(response, 'name="is_active"')

    def test_report_list_wires_machine_component_autocomplete(self) -> None:
        """Machine and component use the forwarding autocomplete widgets."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertContains(response, "/equipment/machines/autocomplete/")
        self.assertContains(response, "/equipment/components/autocomplete/")
        self.assertContains(response, "select2-custom.css")
        self.assertContains(response, "dal-forward-conf-for_id_component")
        self.assertContains(response, '"src": "machine"')

    def test_export_page_renders(self) -> None:
        """The export page renders successfully for authorized users."""
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "id_status")


@override_settings(MEDIA_ROOT=PDF_TEMPLATE_MEDIA_ROOT)
class ReportPDFTemplateTests(TenantSchemaTestCase):
    """The report list and detail expose the PDF when one is stored."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create the temporary media root used by the file field."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, PDF_TEMPLATE_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        """Log in a superuser and create reports with and without a PDF."""
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.report_with_pdf = factories.ReportFactory(
            pdf_file=SimpleUploadedFile(
                "report.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            )
        )
        self.report_without_pdf = factories.ReportFactory()

    def test_list_shows_pdf_badge_and_download_link(self) -> None:
        """A report with a PDF exposes the badge and the download action."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertContains(
            response,
            reverse("apps.reports:report_pdf_download", args=[self.report_with_pdf.pk]),
        )
        self.assertContains(response, ">PDF<")

    def test_list_hides_download_link_without_pdf(self) -> None:
        """A report without a PDF has no download action."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertNotContains(
            response,
            reverse(
                "apps.reports:report_pdf_download", args=[self.report_without_pdf.pk]
            ),
        )

    def test_detail_shows_download_button(self) -> None:
        """The detail page shows the PDF download button."""
        response = self.client.get(
            reverse("apps.reports:report_detail", args=[self.report_with_pdf.pk])
        )
        self.assertContains(
            response,
            reverse("apps.reports:report_pdf_download", args=[self.report_with_pdf.pk]),
        )
        self.assertContains(response, "Descargar PDF")

    def test_detail_hides_button_without_pdf(self) -> None:
        """The detail page omits the PDF button when there is no file."""
        response = self.client.get(
            reverse("apps.reports:report_detail", args=[self.report_without_pdf.pk])
        )
        self.assertNotContains(
            response,
            reverse(
                "apps.reports:report_pdf_download", args=[self.report_without_pdf.pk]
            ),
        )


class ReportsMenuFlagTests(TenantSchemaTestCase):
    """The laboratories menu entry is gated by the feature flag."""

    @override_config(ENABLE_LABS=False)
    def test_menu_hides_laboratory_link_when_flag_disabled(self) -> None:
        """A superuser does not see the laboratory link while the flag is off."""
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertNotContains(response, reverse("apps.reports:laboratory_list"))

    @override_config(ENABLE_LABS=True)
    def test_menu_shows_laboratory_link_when_flag_enabled(self) -> None:
        """A superuser sees the laboratory link when the flag is on."""
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(response, reverse("apps.reports:laboratory_list"))

    @override_config(ENABLE_LABS=False)
    def test_reports_header_hidden_for_view_only_laboratory_user(self) -> None:
        """A view_laboratory-only user sees no orphan reports header when off."""
        user = UserFactory()
        grant_permissions(user, "view_laboratory")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertNotContains(response, "Informes")

    def test_reports_header_visible_for_component_analysis_user(self) -> None:
        """A view_component_analysis-only user still sees the reports header."""
        user = UserFactory()
        grant_permissions(user, "view_component_analysis")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(response, "Informes")


class ReportListFlagTests(TenantSchemaTestCase):
    """The report list laboratory column and filter are gated by the flag."""

    def setUp(self) -> None:
        """Log in a superuser able to view the report list and seed one report."""
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.report = factories.ReportFactory()

    @override_config(ENABLE_LABS=False)
    def test_report_list_hides_laboratory_when_flag_disabled(self) -> None:
        """The report list hides the laboratory filter and column when off."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="laboratory"')
        self.assertNotContains(response, "Laboratorio")
        self.assertNotContains(response, self.report.laboratory.name)

    @override_config(ENABLE_LABS=True)
    def test_report_list_shows_laboratory_when_flag_enabled(self) -> None:
        """The report list shows the laboratory filter and column when on."""
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertContains(response, 'name="laboratory"')
        self.assertContains(response, "Laboratorio")
        self.assertContains(response, self.report.laboratory.name)


class LaboratoryFlagMissingConfigTests(SimpleTestCase):
    """The laboratory gate degrades to falsy when ``config`` is not in context."""

    def test_flag_is_falsy_without_config_in_context(self) -> None:
        """A missing ``config`` object renders the branch as hidden, not an error."""
        template = Template("{% if config.ENABLE_LABS %}on{% else %}off{% endif %}")
        self.assertEqual(template.render(Context({})), "off")


class ReportDetailFlagTests(TenantSchemaTestCase):
    """The report detail laboratory link is gated by the flag."""

    def setUp(self) -> None:
        """Log in a superuser able to view the report detail."""
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)

    @override_config(ENABLE_LABS=False)
    def test_report_detail_disables_laboratory_link_when_flag_disabled(self) -> None:
        """The report detail shows the laboratory as plain text (no link) when off."""
        laboratory = factories.LaboratoryFactory()
        report = factories.ReportFactory(laboratory=laboratory)
        response = self.client.get(
            reverse("apps.reports:report_detail", kwargs={"pk": report.pk})
        )
        self.assertContains(response, laboratory.name)
        self.assertNotContains(
            response,
            reverse("apps.reports:laboratory_detail", kwargs={"pk": laboratory.pk}),
        )

    @override_config(ENABLE_LABS=True)
    def test_report_detail_links_laboratory_when_flag_enabled(self) -> None:
        """The report detail links to the laboratory when on."""
        laboratory = factories.LaboratoryFactory()
        report = factories.ReportFactory(laboratory=laboratory)
        response = self.client.get(
            reverse("apps.reports:report_detail", kwargs={"pk": report.pk})
        )
        self.assertContains(
            response,
            reverse("apps.reports:laboratory_detail", kwargs={"pk": laboratory.pk}),
        )


class ReportExportFlagTests(TenantSchemaTestCase):
    """The export laboratory filter is gated by the flag."""

    def setUp(self) -> None:
        """Log in a superuser able to access the report export page."""
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)

    @override_config(ENABLE_LABS=False)
    def test_export_hides_laboratory_filter_when_flag_disabled(self) -> None:
        """The export page hides the laboratory filter when off."""
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertNotContains(response, 'name="laboratory"')
        self.assertNotContains(response, 'for="id_laboratory"')

    @override_config(ENABLE_LABS=True)
    def test_export_shows_laboratory_filter_when_flag_enabled(self) -> None:
        """The export page shows the laboratory filter when on."""
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertContains(response, 'name="laboratory"')
        self.assertContains(response, 'for="id_laboratory"')


class ComponentAnalysisTemplateContentTests(TenantSchemaTestCase):
    """Static checks for the component analysis template."""

    def test_additives_trend_is_not_hidden_by_component_type(self) -> None:
        """The additives section is available for every component type."""
        template = (
            Path(settings.BASE_DIR)
            / "templates"
            / "reports"
            / "report"
            / "component_analysis.html"
        )
        content = template.read_text(encoding="utf-8")

        self.assertNotIn("showAdditives", content)
        self.assertNotIn("['MOTOR', '']", content)
