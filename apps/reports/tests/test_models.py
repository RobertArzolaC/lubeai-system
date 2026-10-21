"""Tests for the ``apps.reports.models`` module."""

import shutil
import tempfile
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.core.tests.base import TenantSchemaTestCase
from apps.reports import factories, models

PDF_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-report-pdf-")


@override_settings(MEDIA_ROOT=PDF_MEDIA_ROOT)
class ReportPDFModelTests(TenantSchemaTestCase):
    """Tests for the optional PDF attached to a report."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create the temporary media root used by the file field."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, PDF_MEDIA_ROOT, ignore_errors=True)

    def pdf(self, content: bytes = b"%PDF-1.4 test") -> SimpleUploadedFile:
        """Return an uploaded PDF-like file."""
        return SimpleUploadedFile("report.pdf", content, content_type="application/pdf")

    def test_report_has_optional_pdf_file_field(self) -> None:
        """The PDF field is optional and defaults to an empty string."""
        field = models.Report._meta.get_field("pdf_file")
        self.assertTrue(field.blank)
        self.assertFalse(field.null)

    def test_valid_pdf_is_accepted(self) -> None:
        """A file with a PDF header is accepted and stored under an org path."""
        report = factories.ReportFactory()
        report.pdf_file = self.pdf()
        report.full_clean()
        report.save()
        self.assertTrue(report.pdf_file.name.startswith("reports/pdfs/"))
        self.assertTrue(report.pdf_file.name.endswith(".pdf"))

    def test_non_pdf_extension_is_rejected(self) -> None:
        """A file without a PDF extension is rejected."""
        report = factories.ReportFactory.build(
            pdf_file=SimpleUploadedFile("report.txt", b"%PDF-1.4 test")
        )
        with self.assertRaises(ValidationError):
            report.full_clean()

    def test_file_without_pdf_header_is_rejected(self) -> None:
        """A .pdf file with arbitrary content is rejected."""
        report = factories.ReportFactory.build(pdf_file=self.pdf(b"not a real pdf"))
        with self.assertRaises(ValidationError):
            report.full_clean()

    @mock.patch("apps.reports.validators.MAX_REPORT_PDF_SIZE", 10)
    def test_oversized_pdf_is_rejected(self) -> None:
        """A PDF above the configured size limit is rejected."""
        report = factories.ReportFactory.build(
            pdf_file=self.pdf(b"%PDF-1.4 this content is too long")
        )
        with self.assertRaises(ValidationError):
            report.full_clean()

    def test_report_can_be_saved_without_pdf(self) -> None:
        """Reports remain optional for the PDF field."""
        report = factories.ReportFactory()
        self.assertFalse(report.pdf_file)


class LaboratoryModelTests(TenantSchemaTestCase):
    """Tests for the :class:`Laboratory` model."""

    def test_str_returns_name_and_code(self) -> None:
        """The string representation includes the name and code."""
        laboratory = factories.LaboratoryFactory(name="Acme Labs", code="LAB-001")
        self.assertEqual(str(laboratory), "Acme Labs (LAB-001)")

    def test_default_ordering_by_name(self) -> None:
        """Laboratories are ordered alphabetically by name."""
        factories.LaboratoryFactory(name="Zeta")
        factories.LaboratoryFactory(name="Alpha")
        names = list(models.Laboratory.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Alpha", "Zeta"])


class ReportModelTests(TenantSchemaTestCase):
    """Tests for the :class:`Report` model."""

    def test_report_no_longer_has_is_active_field(self) -> None:
        """The report lifecycle is tracked by ``status`` instead of ``is_active``."""
        field_names = {field.name for field in models.Report._meta.get_fields()}
        self.assertNotIn("is_active", field_names)

    def test_str_returns_lab_number_and_condition(self) -> None:
        """The string representation includes the lab number and condition."""
        report = factories.ReportFactory(lab_number="LAB-123", condition="CRITICAL")
        self.assertEqual(
            str(report),
            f"Report {report.lab_number} - {report.get_condition_display()}",
        )

    def test_component_name_returns_type_name(self) -> None:
        """``component_name`` returns the component type name."""
        report = factories.ReportFactory()
        self.assertEqual(report.component_name, report.component.type.name)

    def test_component_name_without_component_is_na(self) -> None:
        """``component_name`` returns ``N/A`` when there is no component."""
        report = factories.ReportFactory(component=None)
        self.assertEqual(report.component_name, "N/A")


class LabAnalysisModelTests(TenantSchemaTestCase):
    """Tests for the computed properties of :class:`LabAnalysis`."""

    def test_total_wear_metals_sums_primary_metals(self) -> None:
        """Wear metal totals sum the six primary metals."""
        analysis = factories.LabAnalysisFactory(
            iron_fe=10,
            chromium_cr=5,
            lead_pb=1,
            copper_cu=2,
            tin_sn=3,
            aluminum_al=4,
        )
        self.assertEqual(analysis.total_wear_metals, 25)

    def test_total_contaminants_sums_contaminants(self) -> None:
        """Contaminant totals sum silicon, sodium and potassium."""
        analysis = factories.LabAnalysisFactory(
            silicon_si=5, sodium_na=4, potassium_k=1
        )
        self.assertEqual(analysis.total_contaminants, 10)

    def test_additive_depletion_pct_none_without_zinc(self) -> None:
        """Additive depletion is ``None`` when zinc is not measured."""
        analysis = factories.LabAnalysisFactory(zinc_zn=None)
        self.assertIsNone(analysis.additive_depletion_pct)

    def test_additive_depletion_pct_is_capped(self) -> None:
        """Additive depletion is capped at 100%."""
        analysis = factories.LabAnalysisFactory(zinc_zn=5000)
        self.assertEqual(analysis.additive_depletion_pct, 100.0)


class AnalysisThresholdModelTests(TenantSchemaTestCase):
    """Tests for the :class:`AnalysisThreshold` model."""

    def test_str_for_global_threshold(self) -> None:
        """Global thresholds show ``Global`` as the component name."""
        threshold = factories.AnalysisThresholdFactory(
            component_type=None,
            category="wear_metals",
            parameter="iron_fe",
        )
        self.assertIn("Global", str(threshold))

    def test_str_for_component_type_threshold(self) -> None:
        """Component-specific thresholds show the component type name."""
        from apps.equipment import factories as equipment_factories

        component_type = equipment_factories.ComponentTypeFactory(name="Pump")
        threshold = factories.AnalysisThresholdFactory(
            component_type=component_type,
            category="wear_metals",
            parameter="iron_fe",
        )
        self.assertIn("Pump", str(threshold))
