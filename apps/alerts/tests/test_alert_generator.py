"""Tests for the report-level alert generation service."""

from django.test import TestCase

from apps.alerts import models
from apps.alerts.services.alert_generator import (
    PARAMETER_FIELD_MAP,
    AlertGeneratorService,
)
from apps.reports import factories as report_factories


def build_analysis(report, **values):
    """Create a LabAnalysis with every mapped field nulled but ``values``."""
    mapped_fields = {field for field, _ in PARAMETER_FIELD_MAP.values()}
    defaults = {field: None for field in mapped_fields}
    defaults.update(values)
    return report_factories.LabAnalysisFactory(report=report, **defaults)


class AlertGeneratorServiceTests(TestCase):
    """Tests for :class:`AlertGeneratorService` report-level consolidation."""

    def setUp(self) -> None:
        self.service = AlertGeneratorService()

    def test_creates_single_alert_per_report(self) -> None:
        """A report with multiple violations yields exactly one alert."""
        report = report_factories.ReportFactory()
        build_analysis(report, iron_fe=120, copper_cu=25)

        alerts = self.service.generate_for_report(report)

        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.report, report)
        self.assertEqual(alert.dedup_key, f"{report.id}:THRESHOLD")
        self.assertEqual(alert.severity, "CRITICAL")
        self.assertEqual(alert.category, "wear_metals")
        self.assertEqual(alert.value, 120.0)

    def test_worst_violation_wins_across_categories(self) -> None:
        """A critical contamination reading beats a caution wear metal."""
        report = report_factories.ReportFactory()
        build_analysis(report, iron_fe=90, silicon_si=40)

        alert = self.service.generate_for_report(report)[0]

        self.assertEqual(alert.severity, "CRITICAL")
        self.assertEqual(alert.category, "contamination")
        self.assertEqual(alert.value, 40.0)

    def test_caution_severity_is_kept(self) -> None:
        """A value above warning but below critical is stored as CAUTION."""
        report = report_factories.ReportFactory()
        build_analysis(report, iron_fe=90)

        alert = self.service.generate_for_report(report)[0]

        self.assertEqual(alert.severity, "CAUTION")
        self.assertEqual(alert.value, 90.0)
        self.assertEqual(alert.warning_limit, 75.0)
        self.assertEqual(alert.critical_limit, 100.0)

    def test_no_alert_when_within_limits(self) -> None:
        """No alert is created when every parameter is below its limits."""
        report = report_factories.ReportFactory()
        build_analysis(report, iron_fe=10, copper_cu=5, silicon_si=5)

        alerts = self.service.generate_for_report(report)

        self.assertEqual(alerts, [])
        self.assertFalse(models.Alert.objects.filter(report=report).exists())

    def test_no_alert_without_analysis(self) -> None:
        """A report without LabAnalysis produces no alerts."""
        report = report_factories.ReportFactory()

        alerts = self.service.generate_for_report(report)

        self.assertEqual(alerts, [])

    def test_generation_is_idempotent(self) -> None:
        """Re-running generation keeps a single alert per report."""
        report = report_factories.ReportFactory()
        build_analysis(report, iron_fe=120)

        self.service.generate_for_report(report)
        alerts = self.service.generate_for_report(report)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(models.Alert.objects.filter(report=report).count(), 1)

    def test_alert_count_matches_reports_with_violations(self) -> None:
        """Dashboard association: one alert per report with any violation."""
        first = report_factories.ReportFactory()
        second = report_factories.ReportFactory()
        clean = report_factories.ReportFactory()
        build_analysis(first, iron_fe=120)
        build_analysis(second, copper_cu=40)
        build_analysis(clean, iron_fe=10, copper_cu=5)

        self.service.generate_for_report(first)
        self.service.generate_for_report(second)
        self.service.generate_for_report(clean)

        self.assertEqual(models.Alert.objects.count(), 2)

    def test_inverse_threshold_flags_low_values(self) -> None:
        """Additives use inverse thresholds: low values trigger the alert."""
        report = report_factories.ReportFactory()
        build_analysis(report, zinc_zn=300)

        alert = self.service.generate_for_report(report)[0]

        self.assertEqual(alert.severity, "CRITICAL")
        self.assertEqual(alert.category, "additives")
        self.assertEqual(alert.unit, "ppm")

    def test_global_threshold_is_preferred_over_fallback(self) -> None:
        """A configured global threshold overrides the hardcoded fallback."""
        report = report_factories.ReportFactory()
        report_factories.AnalysisThresholdFactory(
            component_type=None,
            parameter="lead_pb",
            category="wear_metals",
            warning_limit=25,
            critical_limit=40,
        )
        build_analysis(report, lead_pb=35)

        alert = self.service.generate_for_report(report)[0]

        self.assertEqual(alert.severity, "CAUTION")
        self.assertEqual(alert.critical_limit, 40.0)

    def test_parameter_without_threshold_is_ignored(self) -> None:
        """A mapped field with no threshold/fallback does not raise."""
        report = report_factories.ReportFactory()
        build_analysis(report, iron_fe=120, tin_sn=30)

        alert = self.service.generate_for_report(report)[0]

        self.assertEqual(alert.category, "wear_metals")
        self.assertEqual(alert.value, 120.0)

    def test_inverse_caution_band_and_no_alert(self) -> None:
        """Inverse thresholds flag mid-range values as CAUTION only."""
        caution = report_factories.ReportFactory()
        build_analysis(caution, zinc_zn=700)
        clean = report_factories.ReportFactory()
        build_analysis(clean, zinc_zn=900)

        self.assertEqual(
            self.service.generate_for_report(caution)[0].severity, "CAUTION"
        )
        self.assertEqual(self.service.generate_for_report(clean), [])

    def test_update_refreshes_worst_violation(self) -> None:
        """Re-evaluating a report updates the existing alert's severity."""
        report = report_factories.ReportFactory()
        analysis = build_analysis(report, iron_fe=90)

        self.service.generate_for_report(report)
        analysis.iron_fe = 120
        analysis.save(update_fields=["iron_fe"])
        alerts = self.service.generate_for_report(report)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "CRITICAL")
        self.assertEqual(alerts[0].value, 120.0)

    def test_detected_at_defaults_to_now_without_report_date(self) -> None:
        """Alerts without a report date use the current timestamp."""
        report = report_factories.ReportFactory(report_date=None)
        build_analysis(report, iron_fe=120)

        alert = self.service.generate_for_report(report)[0]

        self.assertIsNotNone(alert.detected_at)

    def test_component_type_threshold_is_preferred(self) -> None:
        """A component-type-specific threshold wins over the global one."""
        report = report_factories.ReportFactory()
        report_factories.AnalysisThresholdFactory(
            component_type=report.component.type,
            parameter="lead_pb",
            category="wear_metals",
            warning_limit=10,
            critical_limit=20,
        )
        build_analysis(report, lead_pb=25)

        alert = self.service.generate_for_report(report)[0]

        self.assertEqual(alert.severity, "CRITICAL")
        self.assertEqual(alert.critical_limit, 20.0)

    def test_resolved_alert_is_reopened(self) -> None:
        """Re-evaluating a resolved report re-opens its alert."""
        report = report_factories.ReportFactory()
        build_analysis(report, iron_fe=120)
        alert = self.service.generate_for_report(report)[0]
        alert.status = "RESOLVED"
        alert.save(update_fields=["status"])

        alert = self.service.generate_for_report(report)[0]

        self.assertEqual(alert.status, "OPEN")

    def test_num_helper_and_evaluate_guard(self) -> None:
        """``_num`` handles empty/non-numeric values; ``_evaluate`` guards."""
        self.assertIsNone(self.service._num(None))
        self.assertIsNone(self.service._num("n/a"))
        self.assertIsNone(
            self.service._evaluate(10, {"warning": None, "critical": None})
        )
