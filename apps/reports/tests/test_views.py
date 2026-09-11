"""Tests for the ``apps.reports.views`` module."""

from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from openpyxl import load_workbook

from apps.equipment import factories as equipment_factories
from apps.reports import factories, models
from apps.users import factories as users_factories

REPORTS_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [settings.BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "reports/laboratory/list.html": "",
                        "reports/laboratory/detail.html": "",
                        "reports/laboratory/form.html": "",
                        "reports/report/list.html": "",
                        "reports/report/detail.html": "",
                        "reports/report/form.html": "",
                        "reports/report/export.html": "",
                        "reports/analysis_threshold/list.html": "",
                        "reports/analysis_threshold/detail.html": "",
                        "reports/analysis_threshold/form.html": "",
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
    """Grant the given reports permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="reports",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)


def report_payload(**overrides: object) -> dict:
    """Build a valid report form payload."""
    machine = equipment_factories.MachineFactory()
    component = equipment_factories.ComponentFactory(machine=machine)
    laboratory = factories.LaboratoryFactory()
    data: dict = {
        "laboratory": laboratory.pk,
        "machine": machine.pk,
        "component": component.pk,
        "lab_number": "LAB-VIEW-1",
        "sample_date": "2024-01-15",
        "status": "PENDING",
        "condition": "NORMAL",
        "is_active": True,
    }
    data.update(overrides)
    return data


@override_settings(TEMPLATES=REPORTS_TEMPLATES)
class LaboratoryViewTests(TestCase):
    """CRUD tests for the Laboratory views."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.laboratory = factories.LaboratoryFactory(name="Acme Labs")

    def test_list_requires_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.get(reverse("apps.reports:laboratory_list"))
        self.assertEqual(response.status_code, 302)

    def test_list_requires_permission(self) -> None:
        """Authenticated users without permission get a 403."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:laboratory_list"))
        self.assertEqual(response.status_code, 403)

    def test_list_renders_with_permission(self) -> None:
        """Authorized users can list laboratories."""
        grant_permissions(self.user, "view_laboratory")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:laboratory_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reports/laboratory/list.html")
        self.assertIn(self.laboratory, response.context["laboratories"])

    def test_list_filters_by_name(self) -> None:
        """The list applies the ``name_search`` filter."""
        other = factories.LaboratoryFactory(name="Beta Labs")
        grant_permissions(self.user, "view_laboratory")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.reports:laboratory_list"), {"name_search": "Acme"}
        )
        self.assertIn(self.laboratory, response.context["laboratories"])
        self.assertNotIn(other, response.context["laboratories"])

    def test_detail_renders(self) -> None:
        """Authorized users can open the laboratory detail."""
        grant_permissions(self.user, "view_laboratory")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.reports:laboratory_detail", kwargs={"pk": self.laboratory.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["laboratory"], self.laboratory)

    def test_create_stamps_author(self) -> None:
        """Creating a laboratory stamps the authoring user."""
        grant_permissions(self.user, "add_laboratory")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.reports:laboratory_create"),
            {
                "name": "New Lab",
                "code": "LAB-NEW",
                "description": "",
                "is_active": True,
            },
        )
        self.assertRedirects(
            response,
            reverse("apps.reports:laboratory_list"),
            fetch_redirect_response=False,
        )
        laboratory = models.Laboratory.objects.get(code="LAB-NEW")
        self.assertEqual(laboratory.created_by, self.user)
        self.assertEqual(laboratory.updated_by, self.user)

    def test_update_changes_laboratory(self) -> None:
        """A valid post updates the laboratory."""
        grant_permissions(self.user, "change_laboratory")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "apps.reports:laboratory_update", kwargs={"pk": self.laboratory.pk}
            ),
            {
                "name": "Renamed Lab",
                "code": self.laboratory.code,
                "description": "",
                "is_active": True,
            },
        )
        self.assertRedirects(
            response,
            reverse("apps.reports:laboratory_list"),
            fetch_redirect_response=False,
        )
        self.laboratory.refresh_from_db()
        self.assertEqual(self.laboratory.name, "Renamed Lab")

    def test_delete_requires_permission(self) -> None:
        """Deleting without permission returns a JSON 403."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.reports:laboratory_delete", kwargs={"pk": self.laboratory.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "error")

    def test_delete_success(self) -> None:
        """Authorized users can delete a laboratory."""
        grant_permissions(self.user, "delete_laboratory")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.reports:laboratory_delete", kwargs={"pk": self.laboratory.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertFalse(
            models.Laboratory.objects.filter(pk=self.laboratory.pk).exists()
        )


@override_settings(TEMPLATES=REPORTS_TEMPLATES)
class ReportViewTests(TestCase):
    """CRUD tests for the Report views."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.report = factories.ReportFactory(status="APPROVED", condition="NORMAL")

    def test_list_renders(self) -> None:
        """Authorized users can list reports."""
        grant_permissions(self.user, "view_report")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reports/report/list.html")
        self.assertIn(self.report, response.context["reports"])

    def test_list_filters_by_status(self) -> None:
        """The report list applies the status filter."""
        other = factories.ReportFactory(status="REJECTED")
        grant_permissions(self.user, "view_report")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.reports:report_list"), {"status": "REJECTED"}
        )
        self.assertIn(other, response.context["reports"])
        self.assertNotIn(self.report, response.context["reports"])

    def test_detail_renders(self) -> None:
        """Authorized users can open the report detail."""
        grant_permissions(self.user, "view_report")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.reports:report_detail", kwargs={"pk": self.report.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["report"], self.report)

    def test_create_post_creates_report(self) -> None:
        """A valid post creates the report."""
        grant_permissions(self.user, "add_report")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.reports:report_create"), report_payload()
        )
        self.assertRedirects(
            response,
            reverse("apps.reports:report_list"),
            fetch_redirect_response=False,
        )
        self.assertTrue(models.Report.objects.filter(lab_number="LAB-VIEW-1").exists())

    def test_update_post_updates_report(self) -> None:
        """A valid post updates the report."""
        grant_permissions(self.user, "change_report")
        self.client.force_login(self.user)
        payload = report_payload(
            laboratory=self.report.laboratory_id,
            machine=self.report.machine_id,
            component=self.report.component_id,
            lab_number=self.report.lab_number,
            recommendations="Updated recommendation",
        )
        response = self.client.post(
            reverse("apps.reports:report_update", kwargs={"pk": self.report.pk}),
            payload,
        )
        self.assertRedirects(
            response,
            reverse("apps.reports:report_list"),
            fetch_redirect_response=False,
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.recommendations, "Updated recommendation")

    def test_delete_success(self) -> None:
        """Authorized users can delete a report."""
        grant_permissions(self.user, "delete_report")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.reports:report_delete", kwargs={"pk": self.report.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_bulk_upload_url_removed(self) -> None:
        """The removed bulk-upload URL is no longer reversed."""
        with self.assertRaises(NoReverseMatch):
            reverse("apps.reports:report_bulk_upload")


@override_settings(TEMPLATES=REPORTS_TEMPLATES)
class AnalysisThresholdViewTests(TestCase):
    """CRUD tests for the AnalysisThreshold views."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.threshold = factories.AnalysisThresholdFactory()

    def test_list_requires_reports_permission(self) -> None:
        """Authorization uses the reports app permissions."""
        grant_permissions(self.user, "view_analysisthreshold")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:analysisthreshold_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reports/analysis_threshold/list.html")

    def test_list_forbidden_without_permission(self) -> None:
        """Users without permission get a 403."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:analysisthreshold_list"))
        self.assertEqual(response.status_code, 403)

    def test_detail_renders(self) -> None:
        """Authorized users can open the threshold detail."""
        grant_permissions(self.user, "view_analysisthreshold")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "apps.reports:analysisthreshold_detail",
                kwargs={"pk": self.threshold.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["threshold"], self.threshold)

    def test_create_post_creates_threshold(self) -> None:
        """A valid post creates the threshold."""
        grant_permissions(self.user, "add_analysisthreshold")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.reports:analysisthreshold_create"),
            {
                "category": "wear_metals",
                "parameter": "iron_fe",
                "warning_limit": 50,
                "critical_limit": 100,
                "unit": "ppm",
                "is_active": True,
            },
        )
        self.assertRedirects(
            response,
            reverse("apps.reports:analysisthreshold_list"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            models.AnalysisThreshold.objects.filter(
                category="wear_metals", parameter="iron_fe"
            ).exists()
        )

    def test_delete_success(self) -> None:
        """Authorized users can delete a threshold."""
        grant_permissions(self.user, "delete_analysisthreshold")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "apps.reports:analysisthreshold_delete",
                kwargs={"pk": self.threshold.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")


@override_settings(TEMPLATES=REPORTS_TEMPLATES)
class ReportExportViewTests(TestCase):
    """Tests for the report export page, preview and download views."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.report = factories.ReportFactory()
        factories.LabAnalysisFactory(report=self.report)

    def test_export_page_renders(self) -> None:
        """The export page renders for authorized users."""
        grant_permissions(self.user, "view_report")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reports/report/export.html")

    def test_export_preview_returns_json(self) -> None:
        """The preview endpoint returns columns and rows as JSON."""
        grant_permissions(self.user, "view_report")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:report_export_preview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(payload["columns"])
        self.assertEqual(len(payload["rows"]), payload["count"])

    def test_export_download_returns_workbook(self) -> None:
        """The download endpoint streams a valid Excel workbook."""
        grant_permissions(self.user, "view_report")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:report_export_download"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        workbook = load_workbook(BytesIO(response.content))
        self.assertIsNotNone(workbook.active)

    def test_export_requires_permission(self) -> None:
        """Users without permission cannot download the export."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:report_export_download"))
        self.assertEqual(response.status_code, 403)


@override_settings(TEMPLATES=REPORTS_TEMPLATES)
class ComponentAnalysisViewTests(TestCase):
    """Tests for the component analysis page and its API endpoints."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.machine = equipment_factories.MachineFactory()
        self.component = equipment_factories.ComponentFactory(machine=self.machine)

    def test_page_renders_with_permission(self) -> None:
        """The page renders and every URL tag resolves for authorized users."""
        grant_permissions(self.user, "view_component_analysis")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:component_analysis"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reports/report/component_analysis.html")
        self.assertContains(response, reverse("apps.reports:analysis_data_api"))
        self.assertContains(response, reverse("apps.reports:analysis_export_pdf"))
        self.assertContains(response, reverse("apps.equipment:autocomplete_component"))

    def test_page_requires_permission(self) -> None:
        """Users without the permission are forbidden."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:component_analysis"))
        self.assertEqual(response.status_code, 403)

    def test_deep_link_seeds_filter(self) -> None:
        """A ``?component`` deep-link preselects machine and component."""
        grant_permissions(self.user, "view_component_analysis")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.reports:component_analysis"),
            {"component": self.component.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["initial_component_id"], self.component.pk)
        self.assertEqual(response.context["initial_machine_id"], self.machine.pk)

    def test_data_api_requires_component(self) -> None:
        """The data API returns 400 when no component is provided."""
        grant_permissions(self.user, "view_component_analysis")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:analysis_data_api"))
        self.assertEqual(response.status_code, 400)

    def test_data_api_missing_component_returns_404(self) -> None:
        """The data API returns 404 for an unknown component."""
        grant_permissions(self.user, "view_component_analysis")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.reports:analysis_data_api"), {"component": 999999}
        )
        self.assertEqual(response.status_code, 404)

    def test_data_api_returns_analysis_payload(self) -> None:
        """The data API returns the full analysis payload for a component."""
        grant_permissions(self.user, "view_component_analysis")
        self.client.force_login(self.user)
        report = factories.ReportFactory(
            component=self.component, machine=self.machine, condition="NORMAL"
        )
        factories.LabAnalysisFactory(report=report)

        response = self.client.get(
            reverse("apps.reports:analysis_data_api"),
            {"component": self.component.pk},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("available_tabs", payload)
        self.assertEqual(payload["summary"]["component_id"], self.component.pk)
        # Dynamic labels must be translated to the active language (es).
        self.assertEqual(payload["available_tabs"][0]["label"], "Resumen")
        self.assertEqual(payload["kpi_metrics"][0]["label"], "Hierro (Fe)")
