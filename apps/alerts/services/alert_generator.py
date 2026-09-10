"""Alert generation services."""

from datetime import datetime, time
from typing import Any

from django.utils import timezone

from apps.alerts.models import Alert
from apps.reports.models import AnalysisThreshold, LabAnalysis, Report

# Maps each parameter to its LabAnalysis field name and report category.
PARAMETER_FIELD_MAP: dict[str, tuple[str, str]] = {
    "iron_fe": ("iron_fe", "wear_metals"),
    "copper_cu": ("copper_cu", "wear_metals"),
    "aluminum_al": ("aluminum_al", "wear_metals"),
    "lead_pb": ("lead_pb", "wear_metals"),
    "chromium_cr": ("chromium_cr", "wear_metals"),
    "tin_sn": ("tin_sn", "wear_metals"),
    "nickel_ni": ("nickel_ni", "wear_metals"),
    "silver_ag": ("silver_ag", "wear_metals"),
    "silicon_si": ("silicon_si", "contamination"),
    "sodium_na": ("sodium_na", "contamination"),
    "potassium_k": ("potassium_k", "contamination"),
    "boron_b": ("boron_b", "contamination"),
    "zinc_zn": ("zinc_zn", "additives"),
    "phosphorus_p": ("phosphorus_p", "additives"),
    "magnesium_mg": ("magnesium_mg", "additives"),
    "calcium_ca": ("calcium_ca", "additives"),
    "oxidation": ("oxidation", "ftir"),
    "nitration": ("nitration", "ftir"),
    "sulfation": ("sulfation", "ftir"),
    "glycol": ("glycol", "ftir"),
    "fuel_dilution": ("fuel_dilution", "ftir"),
    "tbn": ("tbn", "oil_health"),
    "viscosity_100c": ("viscosity_100c", "oil_health"),
    "viscosity_40c": ("viscosity_40c", "oil_health"),
}

# Hardcoded fallback limits used when no AnalysisThreshold is configured.
FALLBACK_THRESHOLDS: dict[str, tuple[float, float, str, bool]] = {
    "iron_fe": (75, 100, "ppm", False),
    "copper_cu": (20, 30, "ppm", False),
    "aluminum_al": (15, 25, "ppm", False),
    "lead_pb": (20, 30, "ppm", False),
    "chromium_cr": (10, 15, "ppm", False),
    "silicon_si": (15, 20, "ppm", False),
    "sodium_na": (30, 50, "ppm", False),
    "potassium_k": (10, 15, "ppm", False),
    "zinc_zn": (800, 600, "ppm", True),
    "phosphorus_p": (900, 700, "ppm", True),
    "magnesium_mg": (1800, 1500, "ppm", True),
    "calcium_ca": (2000, 1500, "ppm", True),
}


class AlertGeneratorService:
    """Generates threshold-based alerts for a report."""

    def generate_for_report(self, report: Report) -> list[Alert]:
        """Generate threshold alerts for a given report.

        Iterates over every mapped parameter and creates an alert whenever the
        measured value exceeds a warning/critical limit. Idempotent by
        ``dedup_key``.

        Args:
            report: The report to evaluate.

        Returns:
            A list of created/updated Alert instances.
        """
        result: list[Alert] = []
        analysis = LabAnalysis.objects.filter(report=report).first()
        if analysis is None:
            return result

        for parameter, (field_name, category) in PARAMETER_FIELD_MAP.items():
            raw_value = getattr(analysis, field_name)
            if raw_value is None:
                continue
            value = float(raw_value)
            threshold = self._find_threshold(report, parameter, category)
            if threshold is None:
                continue
            severity = self._evaluate(value, threshold)
            if severity is None:
                continue
            result.append(
                self._upsert_alert(
                    report, parameter, category, severity, value, threshold
                )
            )
        return result

    def _find_threshold(
        self, report: Report, parameter: str, category: str
    ) -> AnalysisThreshold | dict[str, Any] | None:
        """Resolve the threshold for a parameter.

        Priority: component-type-specific > global > hardcoded fallback.

        Args:
            report: The report being evaluated (used for its component type).
            parameter: The parameter name.
            category: The parameter category.

        Returns:
            An AnalysisThreshold, a fallback dict, or None if none applies.
        """
        component_type = report.component.type if report.component else None
        queryset = AnalysisThreshold.objects.filter(
            is_active=True, category=category, parameter=parameter
        )
        if component_type is not None:
            specific = queryset.filter(component_type=component_type).first()
            if specific:
                return specific
        global_threshold = queryset.filter(component_type__isnull=True).first()
        if global_threshold:
            return global_threshold
        return self._fallback(parameter)

    def _fallback(self, parameter: str) -> dict[str, Any] | None:
        """Return the hardcoded fallback threshold for a parameter, if any."""
        if parameter not in FALLBACK_THRESHOLDS:
            return None
        warning, critical, unit, is_inverse = FALLBACK_THRESHOLDS[parameter]
        return {
            "warning": warning,
            "critical": critical,
            "unit": unit,
            "is_inverse": is_inverse,
        }

    def _evaluate(
        self, value: float, threshold: AnalysisThreshold | dict[str, Any]
    ) -> str | None:
        """Evaluate a value against a threshold and return a severity, if any."""
        warning = self._num(
            threshold.warning_limit
            if hasattr(threshold, "warning_limit")
            else threshold.get("warning")
        )
        critical = self._num(
            threshold.critical_limit
            if hasattr(threshold, "critical_limit")
            else threshold.get("critical")
        )
        is_inverse = bool(
            threshold.is_inverse
            if hasattr(threshold, "is_inverse")
            else threshold.get("is_inverse", False)
        )
        if warning is None or critical is None:
            return None
        if is_inverse:
            if value <= critical:
                return "CRITICAL"
            if value <= warning:
                return "CAUTION"
            return None
        if value >= critical:
            return "CRITICAL"
        if value >= warning:
            return "CAUTION"
        return None

    def _num(self, value: Any) -> float | None:
        """Coerce a value to float, returning None when not possible."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _detected_at(self, report: Report) -> datetime:
        """Resolve an aware timestamp for the alert notification.

        Args:
            report: The source report.

        Returns:
            Timezone-aware datetime (report date at midnight, or now).
        """
        if report.report_date:
            return timezone.make_aware(
                datetime.combine(report.report_date, time.min),
                timezone.get_current_timezone(),
            )
        return timezone.now()

    def _upsert_alert(
        self,
        report: Report,
        parameter: str,
        category: str,
        severity: str,
        value: float,
        threshold: AnalysisThreshold | dict[str, Any],
    ) -> Alert:
        """Create or re-open a threshold alert for a parameter.

        Args:
            report: The source report.
            parameter: The parameter name.
            category: The parameter category.
            severity: The evaluated severity.
            value: The measured value.
            threshold: The resolved threshold (model or fallback dict).

        Returns:
            The Alert instance (created or updated).
        """
        dedup_key = f"{report.id}:{parameter}:THRESHOLD"
        unit = (
            getattr(threshold, "unit", None)
            if hasattr(threshold, "unit")
            else threshold.get("unit")
        ) or "ppm"
        warning = self._num(
            getattr(threshold, "warning_limit", None)
            if hasattr(threshold, "warning_limit")
            else threshold.get("warning")
        )
        critical = self._num(
            getattr(threshold, "critical_limit", None)
            if hasattr(threshold, "critical_limit")
            else threshold.get("critical")
        )
        alert, created = Alert.objects.get_or_create(
            dedup_key=dedup_key,
            defaults={
                "machine": report.machine,
                "component": report.component,
                "report": report,
                "parameter": parameter,
                "category": category,
                "severity": severity,
                "status": "OPEN",
                "value": value,
                "warning_limit": warning,
                "critical_limit": critical,
                "unit": unit,
                "rule_type": "THRESHOLD",
                "detected_at": self._detected_at(report),
            },
        )
        if not created:
            changed = (
                alert.severity != severity
                or alert.value != value
                or alert.status == "RESOLVED"
            )
            if changed:
                alert.severity = severity
                alert.value = value
                if alert.status == "RESOLVED":
                    alert.status = "OPEN"
                alert.save(update_fields=["status", "severity", "value"])
        return alert
