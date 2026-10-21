"""Tests for the report export service."""

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from apps.core.tests.base import TenantSchemaTestCase
from apps.equipment import factories as equipment_factories
from apps.reports import factories, models
from apps.reports.services import ReportExportService
from apps.reports.services.component_analysis import ComponentAnalysisService
from apps.reports.services.dummy_pdf import build_dummy_report_pdf


class DummyReportPDFServiceTests(TenantSchemaTestCase):
    """Tests for the placeholder PDF generator."""

    def test_dummy_pdf_has_pdf_header(self) -> None:
        """The generated document is a valid PDF container."""
        content = build_dummy_report_pdf("INFORME-000001")
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 200)

    def test_dummy_pdf_includes_the_report_number_metadata(self) -> None:
        """Two different reports produce different document sizes/content."""
        first = build_dummy_report_pdf("INFORME-000001")
        second = build_dummy_report_pdf("INFORME-999999")
        self.assertNotEqual(first, second)


class ReportExportServiceTests(TenantSchemaTestCase):
    """Tests for :class:`ReportExportService`."""

    def setUp(self) -> None:
        super().setUp()
        self.report = factories.ReportFactory()
        factories.LabAnalysisFactory(report=self.report)

    def test_preview_returns_columns_and_rows(self) -> None:
        """The preview exposes the column headers and report rows."""
        preview = ReportExportService.preview(models.Report.objects.all())
        self.assertIn("No. Lab", preview["columns"])
        self.assertEqual(len(preview["rows"]), 1)

    def test_preview_respects_limit(self) -> None:
        """The preview honours the requested row limit."""
        factories.ReportFactory.create_batch(3)
        preview = ReportExportService.preview(models.Report.objects.all(), limit=2)
        self.assertEqual(len(preview["rows"]), 2)

    def test_export_to_response_returns_buffer_and_filename(self) -> None:
        """The export returns a workbook buffer and a timestamped filename."""
        buffer, filename = ReportExportService.export_to_response(
            models.Report.objects.all()
        )
        self.assertIsInstance(buffer, BytesIO)
        self.assertTrue(filename.endswith(".xlsx"))

    def test_export_workbook_contains_data(self) -> None:
        """The generated workbook contains a data row for the report."""
        buffer, _ = ReportExportService.export_to_response(models.Report.objects.all())
        workbook = load_workbook(buffer)
        worksheet = workbook.active

        headers = [cell.value for cell in worksheet[5]]
        data_row = [cell.value for cell in worksheet[6]]
        mapping = dict(zip(headers, data_row))

        self.assertEqual(mapping["No. Lab"], self.report.lab_number)

    def test_equipment_columns_are_aligned(self) -> None:
        """The Cliente and Equipo columns map to branch and machine names."""
        buffer, _ = ReportExportService.export_to_response(models.Report.objects.all())
        worksheet = load_workbook(buffer).active

        headers = [cell.value for cell in worksheet[5]]
        data_row = [cell.value for cell in worksheet[6]]
        mapping = dict(zip(headers, data_row))

        self.assertEqual(mapping["Cliente"], self.report.machine.branch.name)
        self.assertEqual(mapping["Equipo"], self.report.machine.name)
        self.assertEqual(mapping["Modelo"], self.report.machine.model)


class ComponentAnalysisUsageCorrelationTests(TenantSchemaTestCase):
    """Tests for the usage/wear correlation series."""

    def setUp(self) -> None:
        super().setUp()
        self.machine = equipment_factories.MachineFactory(measurement_unit="HOURS")
        self.component_type = equipment_factories.ComponentTypeFactory(
            name="Bomba Centrífuga"
        )
        self.component = equipment_factories.ComponentFactory(
            machine=self.machine, type=self.component_type
        )

    def _build_report(self, **overrides: object) -> models.Report:
        """Create a report with its lab analysis for the correlation series."""
        report = factories.ReportFactory(
            machine=self.machine,
            component=self.component,
            sample_date=date(2024, 1, 15),
            **overrides,
        )
        factories.LabAnalysisFactory(report=report, iron_fe=42)
        return report

    def test_uses_lubricant_hours_when_present(self) -> None:
        """The correlation prefers the lubricant hours over machine hours."""
        self._build_report(lubricant_hours=320, machine_hours=1200)

        data = ComponentAnalysisService(self.component.pk).get_usage_correlation()

        self.assertEqual(data["series"][0]["data"][0]["x"], 320.0)

    def test_falls_back_to_machine_hours(self) -> None:
        """Missing lubricant hours fall back to machine hours."""
        self._build_report(lubricant_hours=None, machine_hours=1200)

        data = ComponentAnalysisService(self.component.pk).get_usage_correlation()

        self.assertEqual(data["series"][0]["data"][0]["x"], 1200.0)

    def test_falls_back_to_machine_kms(self) -> None:
        """Missing lubricant kilometres fall back to machine kilometres."""
        self.machine.measurement_unit = "KM"
        self.machine.save(update_fields=["measurement_unit"])
        self._build_report(lubricant_kms=None, machine_kms=45000)

        data = ComponentAnalysisService(self.component.pk).get_usage_correlation()

        self.assertEqual(data["series"][0]["data"][0]["x"], 45000.0)

    def test_additives_trend_is_available_for_non_motor_components(self) -> None:
        """Additives are returned for a non-motor component type."""
        self._build_report(lubricant_hours=320, machine_hours=1200)

        data = ComponentAnalysisService(self.component.pk).get_additives_trend()

        self.assertEqual(len(data["series"]), 4)
