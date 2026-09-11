import logging
from typing import Any, Dict, List, Optional

from apps.equipment import models as equipment_models
from apps.reports import constants, models, utils

logger = logging.getLogger(__name__)


class ComponentAnalysisService:
    """Service for handling component analysis data and calculations."""

    # Fallback threshold constants (used if database is not populated)
    THRESHOLDS = {
        "wear_metals": {
            "iron_fe": {"warning": 75, "critical": 100, "unit": "ppm"},
            "copper_cu": {"warning": 20, "critical": 30, "unit": "ppm"},
            "aluminum_al": {"warning": 15, "critical": 25, "unit": "ppm"},
            "lead_pb": {"warning": 20, "critical": 30, "unit": "ppm"},
            "chromium_cr": {"warning": 10, "critical": 15, "unit": "ppm"},
            "silicon_si": {"warning": 15, "critical": 20, "unit": "ppm"},
            "potassium_k": {"warning": 10, "critical": 15, "unit": "ppm"},
        },
        "contamination": {
            "silicon_si": {"warning": 15, "critical": 20, "unit": "ppm"},
            "sodium_na": {"warning": 30, "critical": 50, "unit": "ppm"},
            "potassium_k": {"warning": 10, "critical": 15, "unit": "ppm"},
        },
        "oil_health": {
            "silicon_si": {"warning": 15, "critical": 20, "unit": "ppm"},
            "sodium_na": {"warning": 30, "critical": 50, "unit": "ppm"},
            "potassium_k": {"warning": 10, "critical": 15, "unit": "ppm"},
            "viscosity_100c": {
                "warning_low": None,
                "warning_high": None,
                "unit": "cSt",
            },
        },
        "additives": {
            "zinc_zn": {"warning": 800, "critical": 600, "unit": "ppm"},
            "phosphorus_p": {"warning": 900, "critical": 700, "unit": "ppm"},
            "magnesium_mg": {"warning": 1800, "critical": 1500, "unit": "ppm"},
            "calcium_ca": {"warning": 2000, "critical": 1500, "unit": "ppm"},
        },
    }

    def __init__(self, component_id: int) -> None:
        """
        Initialize service with component context.

        Args:
            component_id: ID of the component to analyze
        """
        self.component_id = component_id
        self.component: Optional[equipment_models.Component] = None
        self.reports_qs = None
        self._thresholds_cache: Dict[str, Any] = {}
        self._component_type_key: str = ""
        self._load_component()
        self._load_thresholds()

    def _get_component_type_key(self) -> str:
        """
        Get the normalized component type key for this component.

        Returns:
            Normalized component type key (e.g., "MOTOR")
        """
        if self._component_type_key:
            return self._component_type_key

        if self.component and self.component.type:
            self._component_type_key = constants.get_component_type_key(
                self.component.type.name
            )

        return self._component_type_key

    def _load_thresholds(self) -> None:
        """
        Load thresholds from database into cache.

        Priority: Component type-specific thresholds > Global thresholds > Fallback constants.
        """
        try:
            component_type_id = None
            if self.component and self.component.type:
                component_type_id = self.component.type.id

            # First, load global thresholds (component_type is null)
            global_thresholds = models.AnalysisThreshold.objects.filter(
                is_active=True,
                component_type__isnull=True,
            ).values(
                "category",
                "parameter",
                "warning_limit",
                "critical_limit",
                "unit",
                "is_inverse",
                "wear_source_description",
            )

            # Load global thresholds into cache
            for threshold in global_thresholds:
                category = threshold["category"]
                parameter = threshold["parameter"]

                if category not in self._thresholds_cache:
                    self._thresholds_cache[category] = {}

                self._thresholds_cache[category][parameter] = {
                    "warning": threshold["warning_limit"],
                    "critical": threshold["critical_limit"],
                    "unit": threshold["unit"],
                    "is_inverse": threshold["is_inverse"],
                    "wear_source": threshold["wear_source_description"],
                }

            # Then, load component type-specific thresholds (override globals)
            if component_type_id:
                specific_thresholds = models.AnalysisThreshold.objects.filter(
                    is_active=True,
                    component_type_id=component_type_id,
                ).values(
                    "category",
                    "parameter",
                    "warning_limit",
                    "critical_limit",
                    "unit",
                    "is_inverse",
                    "wear_source_description",
                )

                for threshold in specific_thresholds:
                    category = threshold["category"]
                    parameter = threshold["parameter"]

                    if category not in self._thresholds_cache:
                        self._thresholds_cache[category] = {}

                    # Override with component-specific threshold
                    self._thresholds_cache[category][parameter] = {
                        "warning": threshold["warning_limit"],
                        "critical": threshold["critical_limit"],
                        "unit": threshold["unit"],
                        "is_inverse": threshold["is_inverse"],
                        "wear_source": threshold["wear_source_description"],
                    }

            # If no thresholds found in database, use fallback
            if not self._thresholds_cache:
                logger.warning(
                    "No thresholds found in database, using fallback THRESHOLDS constant"
                )
                self._thresholds_cache = self.THRESHOLDS

        except Exception as e:
            logger.error(f"Error loading thresholds from database: {e}")
            self._thresholds_cache = self.THRESHOLDS

    def _get_thresholds(self, category: str) -> Dict[str, Any]:
        """
        Get thresholds for a specific category with colors included.

        Args:
            category: Category name (wear_metals, contamination, etc.)

        Returns:
            Dictionary with threshold data for the category, including colors
        """
        thresholds = self._thresholds_cache.get(category, {})
        enriched_thresholds = {}

        for param_key, threshold_data in thresholds.items():
            enriched_thresholds[param_key] = {
                **threshold_data,
                "color": utils.get_parameter_color(param_key),
            }

        return enriched_thresholds

    def _load_component(self) -> None:
        """Load component and prepare reports queryset."""
        try:
            self.component = equipment_models.Component.objects.select_related("machine", "type").get(
                id=self.component_id, is_active=True
            )

            # Base queryset: reports for this component with analysis data
            self.reports_qs = (
                models.Report.objects.filter(
                    component=self.component,
                    is_active=True,
                    sample_date__isnull=False,
                )
                .select_related("analysis")
                .order_by("sample_date")
            )

        except equipment_models.Component.DoesNotExist:
            logger.error(f"Component {self.component_id} not found or inactive")
            raise ValueError(f"Component {self.component_id} not found")

    def get_component_summary(self) -> Dict[str, Any]:
        """
        Get summary information about the component.

        Returns:
            Dictionary with component details and measurement unit
        """
        if not self.component:
            return {}

        latest_report = self.reports_qs.last()
        measurement_unit = self.detect_measurement_unit()

        return {
            "component_id": self.component.id,
            "component_type": (
                self.component.type.name if self.component.type else "N/A"
            ),
            "component_type_key": self._get_component_type_key(),
            "machine_name": self.component.machine.name,
            "machine_serial": self.component.machine.serial_number,
            "machine_model": self.component.machine.model,
            "total_reports": self.reports_qs.count(),
            "latest_sample_date": (
                latest_report.sample_date.strftime("%Y-%m-%d")
                if latest_report
                else None
            ),
            "measurement_unit": measurement_unit,
        }

    def detect_measurement_unit(self) -> str:
        """
        Detect if the machine uses hours or kilometers as measurement unit.

        Uses the Machine.measurement_unit field if available.

        Returns:
            "hours" or "kilometers" based on machine configuration
        """
        if self.component and self.component.machine:
            unit = self.component.machine.measurement_unit
            if unit == "KM":
                return "kilometers"
            elif unit == "HOURS":
                return "hours"
            elif unit == "BOTH":
                # Check which field has more data
                reports = self.reports_qs.all()
                hours_count = sum(1 for r in reports if r.lubricant_hours is not None)
                kms_count = sum(1 for r in reports if r.lubricant_kms is not None)
                return "kilometers" if kms_count > hours_count else "hours"

        return "hours"

    def _calculate_parameter_status(
        self, value: Optional[float], param_key: str, category: str
    ) -> str:
        """
        Calculate the status (normal/caution/critical) for a parameter value.

        Args:
            value: The parameter value
            param_key: The parameter key (e.g., "iron_fe")
            category: The category (e.g., "wear_metals")

        Returns:
            Status string: "normal", "caution", or "critical"
        """
        if value is None:
            return "normal"

        thresholds = self._thresholds_cache.get(category, {})
        threshold = thresholds.get(param_key, {})

        if not threshold:
            return "normal"

        warning = threshold.get("warning")
        critical = threshold.get("critical")
        is_inverse = threshold.get("is_inverse", False)

        if warning is None or critical is None:
            return "normal"

        if is_inverse:
            # Lower values are worse (e.g., additives depleting)
            if value <= critical:
                return "critical"
            elif value <= warning:
                return "caution"
            else:
                return "normal"
        else:
            # Higher values are worse (e.g., wear metals)
            if value >= critical:
                return "critical"
            elif value >= warning:
                return "caution"
            else:
                return "normal"

    def calculate_overall_status(self) -> Dict[str, Any]:
        """
        Calculate the overall status of the component based on latest analysis.

        Returns:
            Dictionary with status, color, label, and recommendation
        """
        latest_report = self.reports_qs.filter(analysis__isnull=False).last()

        if not latest_report:
            return {
                "status": "normal",
                "color": constants.STATUS_COLORS["normal"],
                "label": constants.STATUS_LABELS["normal"],
                "recommendation": "Sin datos de análisis disponibles.",
            }

        # Determine overall status
        current_condition = latest_report.condition.lower()
        if "critical" == current_condition:
            overall_status = "critical"
            recommendation = (
                "Se requiere atención inmediata. "
                "Revisar componente y considerar cambio de lubricante."
            )
        elif "caution" == current_condition:
            overall_status = "caution"
            recommendation = (
                "Monitorear de cerca. "
                "Programar inspección y reducir intervalo de muestreo."
            )
        else:
            overall_status = "normal"
            recommendation = (
                "Componente en condición normal. "
                "Continuar con el programa de mantenimiento establecido."
            )

        return {
            "status": overall_status,
            "color": constants.STATUS_COLORS[overall_status],
            "label": constants.STATUS_LABELS[overall_status],
            "recommendation": recommendation,
        }

    def _calculate_trend(self, values: List[Optional[float]]) -> Dict[str, Any]:
        """
        Calculate the trend direction for a series of values.

        Args:
            values: List of values (most recent last)

        Returns:
            Dictionary with trend direction and percentage
        """
        # Filter out None values
        valid_values = [v for v in values if v is not None]

        if len(valid_values) < 2:
            return {"direction": "stable", "percentage": 0}

        # Compare last two values
        current = valid_values[-1]
        previous = valid_values[-2]

        if previous == 0:
            if current > 0:
                return {"direction": "up", "percentage": 100}
            else:
                return {"direction": "stable", "percentage": 0}

        percentage = ((current - previous) / abs(previous)) * 100

        if current > previous:
            direction = "up"
        elif current < previous:
            direction = "down"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "percentage": round(abs(percentage), 1),
        }

    def get_kpi_metrics(self) -> List[Dict[str, Any]]:
        """
        Get KPI metrics for the overview tab.

        Returns:
            List of KPI dictionaries with value, status, trend, and label
        """
        reports = list(self.reports_qs.filter(analysis__isnull=False))
        kpi_params = constants.get_kpi_parameters_for_component_type(
            self.component.type.name if self.component and self.component.type else ""
        )

        kpis = []
        param_data = self._extract_parameter_data(reports, kpi_params)

        for param_key in kpi_params:
            values = param_data.get(param_key, [])
            current_value = values[-1] if values else None

            # Determine category for status calculation
            category = self._get_category_for_parameter(param_key)
            status = self._calculate_parameter_status(
                current_value, param_key, category
            )
            trend = self._calculate_trend(values)

            # Get threshold info
            thresholds = self._thresholds_cache.get(category, {})
            threshold_info = thresholds.get(param_key, {})

            kpis.append(
                {
                    "parameter": param_key,
                    "label": constants.PARAMETER_LABELS.get(param_key, param_key),
                    "value": round(current_value, 2)
                    if current_value is not None
                    else None,
                    "unit": threshold_info.get("unit", "ppm"),
                    "status": status,
                    "color": constants.STATUS_COLORS[status],
                    "trend": trend,
                    "warning": threshold_info.get("warning"),
                    "critical": threshold_info.get("critical"),
                }
            )

        return kpis

    def _get_category_for_parameter(self, param_key: str) -> str:
        """
        Determine the category for a given parameter key.

        Args:
            param_key: The parameter key

        Returns:
            Category name
        """
        wear_metals = [
            "iron_fe",
            "copper_cu",
            "aluminum_al",
            "lead_pb",
            "chromium_cr",
        ]
        contamination = ["silicon_si", "sodium_na", "potassium_k"]
        additives = ["zinc_zn", "phosphorus_p", "magnesium_mg", "calcium_ca"]

        if param_key in wear_metals:
            return "wear_metals"
        elif param_key in contamination:
            return "contamination"
        elif param_key in additives:
            return "additives"
        else:
            return "oil_health"

    def _extract_parameter_data(
        self, reports: List, params: List[str]
    ) -> Dict[str, List[Optional[float]]]:
        """
        Extract parameter values from reports.

        Args:
            reports: List of Report objects
            params: List of parameter keys to extract

        Returns:
            Dictionary mapping parameter keys to lists of values
        """
        data: Dict[str, List[Optional[float]]] = {p: [] for p in params}

        for report in reports:
            if not hasattr(report, "analysis"):
                continue
            analysis = report.analysis

            for param_key in params:
                value = getattr(analysis, param_key, None)
                data[param_key].append(float(value) if value is not None else None)

        return data

    def get_wear_metals_radar(self) -> Dict[str, Any]:
        """
        Get wear metals data for radar chart.

        Returns:
            Dictionary with labels, current values, and threshold references
        """
        latest_report = self.reports_qs.filter(analysis__isnull=False).last()
        wear_metals = constants.WEAR_METALS_RADAR

        labels = []
        values = []
        max_values = []  # For normalizing to 100% scale

        if latest_report and hasattr(latest_report, "analysis"):
            analysis = latest_report.analysis
            wear_thresholds = self._get_thresholds("wear_metals")
            contamination_thresholds = self._get_thresholds("contamination")

            for metal in wear_metals:
                value = getattr(analysis, metal, None)
                threshold = wear_thresholds.get(
                    metal, {}
                ) or contamination_thresholds.get(metal, {})
                critical = threshold.get("critical", 100)

                labels.append(constants.PARAMETER_LABELS.get(metal, metal))

                if value is not None:
                    # Normalize to percentage of critical limit
                    normalized = min((float(value) / critical) * 100, 150)
                    values.append(round(normalized, 1))
                else:
                    values.append(0)

                max_values.append(100)  # 100% = critical limit

        return {
            "labels": labels,
            "series": [
                {
                    "name": "Valor Actual",
                    "data": values,
                },
            ],
            "annotations": {
                "warning": 75,  # 75% of critical = warning
                "critical": 100,  # 100% = critical
            },
        }

    def get_usage_correlation(self) -> Dict[str, Any]:
        """
        Get usage vs wear correlation data.

        Returns:
            Dictionary with scatter plot data for usage vs wear
        """
        reports = list(self.reports_qs.filter(analysis__isnull=False))
        measurement_unit = self.detect_measurement_unit()

        data_points = []

        for report in reports:
            analysis = report.analysis

            # Get usage value based on measurement unit
            if measurement_unit == "hours":
                usage = report.lubricant_hours
                usage_label = "Horas"
            else:
                usage = report.lubricant_kms
                usage_label = "Kilómetros"

            if usage is None:
                continue

            # Use iron as primary wear indicator
            iron_value = analysis.iron_fe if analysis.iron_fe is not None else 0

            data_points.append(
                {
                    "x": float(usage),
                    "y": float(iron_value),
                    "date": report.sample_date.strftime("%Y-%m-%d"),
                }
            )

        return {
            "series": [
                {
                    "name": "Fe vs Uso",
                    "data": data_points,
                }
            ],
            "x_axis_label": usage_label if data_points else "Uso",
            "y_axis_label": "Hierro (Fe) ppm",
            "measurement_unit": measurement_unit,
        }

    def get_wear_sources(self) -> Dict[str, str]:
        """
        Get wear source descriptions for the component type.

        Returns:
            Dictionary mapping parameter keys to wear source descriptions
        """
        # First check thresholds cache for wear sources
        wear_sources = {}

        for category in ["wear_metals", "contamination"]:
            thresholds = self._thresholds_cache.get(category, {})
            for param_key, threshold_data in thresholds.items():
                wear_source = threshold_data.get("wear_source", "")
                if wear_source:
                    wear_sources[param_key] = wear_source

        # Fall back to constants if not in database
        if not wear_sources:
            component_type_name = (
                self.component.type.name
                if self.component and self.component.type
                else ""
            )
            wear_sources = constants.get_wear_sources_for_component_type(
                component_type_name
            )

        return wear_sources

    def get_available_tabs(self) -> List[Dict[str, str]]:
        """
        Get available tabs for this component type.

        Returns:
            List of tab dictionaries with id and label
        """
        component_type_name = (
            self.component.type.name if self.component and self.component.type else ""
        )
        return constants.get_tabs_for_component_type(component_type_name)

    def get_wear_trends(self) -> Dict[str, Any]:
        """
        Get wear metal trends data (Fe, Cu, Al).

        Returns:
            Dictionary with series data and thresholds
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        data_series = {
            "iron_fe": [],
            "copper_cu": [],
            "aluminum_al": [],
        }
        dates = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))

                data_series["iron_fe"].append(
                    float(analysis.iron_fe) if analysis.iron_fe is not None else None
                )
                data_series["copper_cu"].append(
                    float(analysis.copper_cu)
                    if analysis.copper_cu is not None
                    else None
                )
                data_series["aluminum_al"].append(
                    float(analysis.aluminum_al)
                    if analysis.aluminum_al is not None
                    else None
                )

        return {
            "dates": dates,
            "series": [
                {
                    "name": "Hierro (Fe)",
                    "data": data_series["iron_fe"],
                    "color": utils.get_parameter_color("iron_fe"),
                },
                {
                    "name": "Cobre (Cu)",
                    "data": data_series["copper_cu"],
                    "color": utils.get_parameter_color("copper_cu"),
                },
                {
                    "name": "Aluminio (Al)",
                    "data": data_series["aluminum_al"],
                    "color": utils.get_parameter_color("aluminum_al"),
                },
            ],
            "thresholds": self._get_thresholds("wear_metals"),
        }

    def get_contamination_alerts(self) -> Dict[str, Any]:
        """
        Get contamination data (Si, Na, K).

        Returns:
            Dictionary with series data and thresholds
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        data_series = {
            "silicon_si": [],
            "sodium_na": [],
            "potassium_k": [],
        }
        dates = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))

                data_series["silicon_si"].append(
                    float(analysis.silicon_si)
                    if analysis.silicon_si is not None
                    else None
                )
                data_series["sodium_na"].append(
                    float(analysis.sodium_na)
                    if analysis.sodium_na is not None
                    else None
                )
                data_series["potassium_k"].append(
                    float(analysis.potassium_k)
                    if analysis.potassium_k is not None
                    else None
                )

        return {
            "dates": dates,
            "series": [
                {
                    "name": "Silicio (Si) - Polvo",
                    "data": data_series["silicon_si"],
                    "color": utils.get_parameter_color("silicon_si"),
                },
                {
                    "name": "Sodio (Na) - Refrigerante",
                    "data": data_series["sodium_na"],
                    "color": utils.get_parameter_color("sodium_na"),
                },
                {
                    "name": "Potasio (K)",
                    "data": data_series["potassium_k"],
                    "color": utils.get_parameter_color("potassium_k"),
                },
            ],
            "thresholds": self._get_thresholds("contamination"),
        }

    def get_oil_health(self) -> Dict[str, Any]:
        """
        Get oil health indicators (Si, Na, K, viscosity) with lubricant usage.

        Returns:
            Dictionary with series data, thresholds, and lubricant usage data
        """
        reports = self.reports_qs.filter(analysis__isnull=False)
        measurement_unit = self.detect_measurement_unit()

        data_series = {
            "silicon_si": [],
            "sodium_na": [],
            "potassium_k": [],
            "viscosity_100c": [],
            "lubricant_usage": [],
        }
        dates = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))

                data_series["silicon_si"].append(
                    float(analysis.silicon_si)
                    if analysis.silicon_si is not None
                    else None
                )
                data_series["sodium_na"].append(
                    float(analysis.sodium_na)
                    if analysis.sodium_na is not None
                    else None
                )
                data_series["potassium_k"].append(
                    float(analysis.potassium_k)
                    if analysis.potassium_k is not None
                    else None
                )
                data_series["viscosity_100c"].append(
                    float(analysis.viscosity_100c)
                    if analysis.viscosity_100c is not None
                    else None
                )

                # Lubricant usage data for bar chart
                if measurement_unit == "hours":
                    lubricant_value = (
                        float(report.lubricant_hours)
                        if report.lubricant_hours is not None
                        else None
                    )
                else:
                    lubricant_value = (
                        float(report.lubricant_kms)
                        if report.lubricant_kms is not None
                        else None
                    )
                data_series["lubricant_usage"].append(lubricant_value)

        unit_label = "Horas" if measurement_unit == "hours" else "Kilómetros"

        return {
            "dates": dates,
            "measurement_unit": measurement_unit,
            "unit_label": unit_label,
            "series": [
                {
                    "name": f"Lubricante ({unit_label})",
                    "data": data_series["lubricant_usage"],
                    "color": "#A1A5B7",
                    "type": "column",
                },
                {
                    "name": "Silicio (Si) - ppm",
                    "data": data_series["silicon_si"],
                    "color": utils.get_parameter_color("silicon_si"),
                    "type": "line",
                },
                {
                    "name": "Sodio (Na) - ppm",
                    "data": data_series["sodium_na"],
                    "color": utils.get_parameter_color("sodium_na"),
                    "type": "line",
                },
                {
                    "name": "Potasio (K) - ppm",
                    "data": data_series["potassium_k"],
                    "color": utils.get_parameter_color("potassium_k"),
                    "type": "line",
                },
                {
                    "name": "Viscosidad @ 100°C (cSt)",
                    "data": data_series["viscosity_100c"],
                    "color": utils.get_parameter_color("viscosity_100c"),
                    "type": "line",
                },
            ],
            "thresholds": self._get_thresholds("oil_health"),
        }

    def get_additives_trend(self) -> Dict[str, Any]:
        """
        Get additive elements trend (Zn, P, Mg, Ca).

        Returns:
            Dictionary with series data and thresholds
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        data_series = {
            "zinc_zn": [],
            "phosphorus_p": [],
            "magnesium_mg": [],
            "calcium_ca": [],
        }
        dates = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))

                data_series["zinc_zn"].append(
                    float(analysis.zinc_zn) if analysis.zinc_zn is not None else None
                )
                data_series["phosphorus_p"].append(
                    float(analysis.phosphorus_p)
                    if analysis.phosphorus_p is not None
                    else None
                )
                data_series["magnesium_mg"].append(
                    float(analysis.magnesium_mg)
                    if analysis.magnesium_mg is not None
                    else None
                )
                data_series["calcium_ca"].append(
                    float(analysis.calcium_ca)
                    if analysis.calcium_ca is not None
                    else None
                )

        return {
            "dates": dates,
            "series": [
                {
                    "name": "Zinc (Zn)",
                    "data": data_series["zinc_zn"],
                    "color": utils.get_parameter_color("zinc_zn"),
                },
                {
                    "name": "Fósforo (P)",
                    "data": data_series["phosphorus_p"],
                    "color": utils.get_parameter_color("phosphorus_p"),
                },
                {
                    "name": "Magnesio (Mg)",
                    "data": data_series["magnesium_mg"],
                    "color": utils.get_parameter_color("magnesium_mg"),
                },
                {
                    "name": "Calcio (Ca)",
                    "data": data_series["calcium_ca"],
                    "color": utils.get_parameter_color("calcium_ca"),
                },
            ],
            "thresholds": self._get_thresholds("additives"),
        }

    def _find_threshold_for_parameter(self, param_key: str) -> Dict[str, Any]:
        """
        Search for a parameter's threshold across all cached categories.

        Args:
            param_key: The parameter key to search for (e.g., "pq_index")

        Returns:
            Threshold dictionary with warning/critical keys, or empty dict if not found
        """
        for cat_thresholds in self._thresholds_cache.values():
            if param_key in cat_thresholds:
                return cat_thresholds[param_key]
        return {}

    def get_tbn_tan_trend(self) -> Dict[str, Any]:
        """
        Get TBN and TAN trend data for the advanced tab.

        Returns:
            Dictionary with dates, tbn values, and tan values
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        dates = []
        tbn_values: List[Optional[float]] = []
        tan_values: List[Optional[float]] = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))
                tbn_values.append(
                    float(analysis.tbn) if analysis.tbn is not None else None
                )
                tan_values.append(
                    float(analysis.tan) if analysis.tan is not None else None
                )

        return {
            "dates": dates,
            "tbn": tbn_values,
            "tan": tan_values,
        }

    def get_ftir_trends(self) -> Dict[str, Any]:
        """
        Get FTIR analysis trends (oxidation, nitration, sulfation) for the advanced tab.

        Returns:
            Dictionary with dates and oxidation, nitration, sulfation value arrays
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        dates = []
        oxidation_values: List[Optional[float]] = []
        nitration_values: List[Optional[float]] = []
        sulfation_values: List[Optional[float]] = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))
                oxidation_values.append(
                    float(analysis.oxidation)
                    if analysis.oxidation is not None
                    else None
                )
                nitration_values.append(
                    float(analysis.nitration)
                    if analysis.nitration is not None
                    else None
                )
                sulfation_values.append(
                    float(analysis.sulfation)
                    if analysis.sulfation is not None
                    else None
                )

        return {
            "dates": dates,
            "oxidation": oxidation_values,
            "nitration": nitration_values,
            "sulfation": sulfation_values,
        }

    def get_particle_distribution(self) -> Dict[str, Any]:
        """
        Get particle size distribution trends for the advanced tab.

        Returns:
            Dictionary with dates and arrays for each particle size channel
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        dates = []
        particle_fields = [
            "particle_4um",
            "particle_6um",
            "particle_14um",
            "particle_21um",
            "particle_38um",
            "particle_70um",
        ]
        data_series: Dict[str, List[Optional[float]]] = {
            field: [] for field in particle_fields
        }

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))
                for field in particle_fields:
                    value = getattr(analysis, field, None)
                    data_series[field].append(
                        float(value) if value is not None else None
                    )

        return {
            "dates": dates,
            **data_series,
        }

    def get_pq_index_trend(self) -> Dict[str, Any]:
        """
        Get PQ Index trend data with threshold limits for the advanced tab.

        Returns:
            Dictionary with dates, values, warning_limit, and critical_limit
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        dates = []
        values: List[Optional[float]] = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))
                values.append(
                    float(analysis.pq_index) if analysis.pq_index is not None else None
                )

        threshold = self._find_threshold_for_parameter("pq_index")
        warning_limit = threshold.get("warning")
        critical_limit = threshold.get("critical")

        return {
            "dates": dates,
            "values": values,
            "warning_limit": float(warning_limit)
            if warning_limit is not None
            else None,
            "critical_limit": float(critical_limit)
            if critical_limit is not None
            else None,
        }

    def get_fuel_dilution_trend(self) -> Dict[str, Any]:
        """
        Get fuel dilution trend data with threshold limits for the advanced tab.

        Returns:
            Dictionary with dates, values, warning_limit, and critical_limit
        """
        reports = self.reports_qs.filter(analysis__isnull=False)

        dates = []
        values: List[Optional[float]] = []

        for report in reports:
            if hasattr(report, "analysis"):
                analysis = report.analysis
                dates.append(report.sample_date.strftime("%Y-%m-%d"))
                values.append(
                    float(analysis.fuel_dilution)
                    if analysis.fuel_dilution is not None
                    else None
                )

        threshold = self._find_threshold_for_parameter("fuel_dilution")
        warning_limit = threshold.get("warning")
        critical_limit = threshold.get("critical")

        return {
            "dates": dates,
            "values": values,
            "warning_limit": float(warning_limit)
            if warning_limit is not None
            else None,
            "critical_limit": float(critical_limit)
            if critical_limit is not None
            else None,
        }

    def get_single_parameter_trend(self, parameter_name: str) -> Dict[str, Any]:
        """
        Get time-series trend data for a single parameter.

        Extracts historical values for one parameter from all reports with
        analysis data, calculates trend direction, current status vs thresholds,
        and returns a structured dict ready for chat formatting.

        Args:
            parameter_name: Field name of the parameter (e.g., "iron_fe", "viscosity_100c")

        Returns:
            Dictionary with dates, values, trend, status, thresholds, unit, and total count
        """
        reports = list(self.reports_qs.filter(analysis__isnull=False))

        dates = [r.sample_date.strftime("%Y-%m-%d") for r in reports]
        param_data = self._extract_parameter_data(reports, [parameter_name])
        values = param_data.get(parameter_name, [])

        trend = self._calculate_trend(values)

        # Current value: last non-None value
        current_value: Optional[float] = None
        for v in reversed(values):
            if v is not None:
                current_value = v
                break

        category = self._get_category_for_parameter(parameter_name)
        status = self._calculate_parameter_status(
            current_value, parameter_name, category
        )

        threshold = self._find_threshold_for_parameter(parameter_name)
        unit = threshold.get("unit", "ppm")

        return {
            "parameter": parameter_name,
            "label": constants.PARAMETER_LABELS.get(parameter_name, parameter_name),
            "dates": dates,
            "values": values,
            "current_value": round(current_value, 2)
            if current_value is not None
            else None,
            "unit": unit,
            "status": status,
            "trend": trend,
            "warning": threshold.get("warning"),
            "critical": threshold.get("critical"),
            "total_data_points": len([v for v in values if v is not None]),
        }

    def get_all_analysis_data(self) -> Dict[str, Any]:
        """
        Get complete analysis data including summary and all charts.

        Returns:
            Dictionary with all component analysis data
        """
        try:
            return {
                "summary": self.get_component_summary(),
                "status": self.calculate_overall_status(),
                "kpi_metrics": self.get_kpi_metrics(),
                "available_tabs": self.get_available_tabs(),
                "wear_radar": self.get_wear_metals_radar(),
                "wear_trends": self.get_wear_trends(),
                "contamination": self.get_contamination_alerts(),
                "oil_health": self.get_oil_health(),
                "additives": self.get_additives_trend(),
                "usage_correlation": self.get_usage_correlation(),
                "wear_sources": self.get_wear_sources(),
                "thresholds": self._thresholds_cache,
                "tbn_tan": self.get_tbn_tan_trend(),
                "ftir_trends": self.get_ftir_trends(),
                "particle_distribution": self.get_particle_distribution(),
                "pq_index_trend": self.get_pq_index_trend(),
                "fuel_dilution_trend": self.get_fuel_dilution_trend(),
            }
        except Exception:
            logger.exception(
                f"Error getting analysis data for component {self.component_id}"
            )
            raise
