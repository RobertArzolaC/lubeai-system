import logging
from io import BytesIO
from typing import Any, ClassVar

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _
from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from apps.reports import models

logger = logging.getLogger(__name__)


class ReportExportService:
    """
    Service for exporting report data to Excel format.

    Provides methods for generating professional Excel exports with
    complete inspection data including lab analysis results.
    """

    # Column configuration with headers and field mappings
    COLUMN_CONFIG: ClassVar[list[dict[str, Any]]] = [
        # Report identification
        {"header": "N°", "width": 6, "category": "id"},
        {"header": "No. Lab", "width": 12, "category": "id"},
        {"header": "No. PER", "width": 12, "category": "id"},
        # Laboratory
        {"header": "Laboratorio", "width": 20, "category": "id"},
        # Equipment
        {"header": "Cliente", "width": 25, "category": "equipo"},
        {"header": "Equipo", "width": 20, "category": "equipo"},
        {"header": "Modelo", "width": 18, "category": "equipo"},
        {"header": "No. Serie Equipo", "width": 18, "category": "equipo"},
        {"header": "Componente", "width": 18, "category": "equipo"},
        {"header": "Cód/Núm Serie", "width": 16, "category": "equipo"},
        # Lubricant and usage
        {"header": "Lubricante", "width": 22, "category": "lubricante"},
        {"header": "Equipo Horas", "width": 12, "category": "lubricante"},
        {"header": "Equipo Kms", "width": 12, "category": "lubricante"},
        {"header": "Lubricante Horas", "width": 14, "category": "lubricante"},
        {"header": "Lubricante Kms", "width": 14, "category": "lubricante"},
        # Dates
        {"header": "Fecha Muestra", "width": 14, "category": "fechas"},
        {"header": "Fecha Recepción", "width": 14, "category": "fechas"},
        {"header": "Fecha Reporte", "width": 14, "category": "fechas"},
        # Status and condition
        {"header": "Estado", "width": 12, "category": "estado"},
        {"header": "Condición", "width": 12, "category": "estado"},
        {"header": "Cambio Filtro", "width": 12, "category": "estado"},
        {"header": "Cambio Aceite", "width": 12, "category": "estado"},
        # Water tests
        {"header": "Agua (Crackle)", "width": 14, "category": "agua"},
        {"header": "Agua Destilación (%)", "width": 16, "category": "agua"},
        {"header": "Refrigerante (%)", "width": 14, "category": "agua"},
        # Viscosity
        {
            "header": "Viscosidad 40°C (cSt)",
            "width": 18,
            "category": "viscosidad",
        },
        {
            "header": "Viscosidad 100°C (cSt)",
            "width": 18,
            "category": "viscosidad",
        },
        {"header": "Índice de Viscosidad", "width": 16, "category": "viscosidad"},
        # Acid/Base numbers
        {"header": "TBN (mgKOH/g)", "width": 14, "category": "acido_base"},
        {"header": "TAN (mgKOH/g)", "width": 14, "category": "acido_base"},
        {"header": "Compatibilidad", "width": 14, "category": "acido_base"},
        # FTIR Analysis
        {"header": "Oxidación (Abs/cm)", "width": 16, "category": "ftir"},
        {"header": "Hollín (%)", "width": 12, "category": "ftir"},
        {"header": "Nitración (Abs/cm)", "width": 16, "category": "ftir"},
        {"header": "Sulfatación (Abs/cm)", "width": 16, "category": "ftir"},
        {"header": "Glicol (%)", "width": 12, "category": "ftir"},
        {"header": "Dilución Combustible (%)", "width": 18, "category": "ftir"},
        {"header": "Agua FTIR (%)", "width": 12, "category": "ftir"},
        # Particle analysis
        {"header": "PQ Index", "width": 10, "category": "particulas"},
        {"header": "Conteo ISO", "width": 14, "category": "particulas"},
        {"header": "Part. < 4µm (c/mL)", "width": 16, "category": "particulas"},
        {"header": "Part. < 6µm (c/mL)", "width": 16, "category": "particulas"},
        {"header": "Part. < 14µm (c/mL)", "width": 16, "category": "particulas"},
        {"header": "Part. < 21µm (c/mL)", "width": 16, "category": "particulas"},
        {"header": "Part. < 38µm (c/mL)", "width": 16, "category": "particulas"},
        {"header": "Part. < 70µm (c/mL)", "width": 16, "category": "particulas"},
        # Wear metals (ppm)
        {"header": "Hierro Fe (ppm)", "width": 14, "category": "desgaste"},
        {"header": "Cromo Cr (ppm)", "width": 14, "category": "desgaste"},
        {"header": "Plomo Pb (ppm)", "width": 14, "category": "desgaste"},
        {"header": "Cobre Cu (ppm)", "width": 14, "category": "desgaste"},
        {"header": "Estaño Sn (ppm)", "width": 14, "category": "desgaste"},
        {"header": "Aluminio Al (ppm)", "width": 14, "category": "desgaste"},
        {"header": "Níquel Ni (ppm)", "width": 14, "category": "desgaste"},
        {"header": "Plata Ag (ppm)", "width": 14, "category": "desgaste"},
        # Contaminants (ppm)
        {
            "header": "Silicio Si (ppm)",
            "width": 14,
            "category": "contaminantes",
        },
        {"header": "Boro B (ppm)", "width": 12, "category": "contaminantes"},
        {"header": "Sodio Na (ppm)", "width": 14, "category": "contaminantes"},
        {"header": "Potasio K (ppm)", "width": 14, "category": "contaminantes"},
        {"header": "Dispersancia", "width": 14, "category": "contaminantes"},
        {"header": "Spot Test", "width": 16, "category": "contaminantes"},
        # Additives (ppm)
        {"header": "Magnesio Mg (ppm)", "width": 16, "category": "aditivos"},
        {"header": "Molibdeno Mo (ppm)", "width": 16, "category": "aditivos"},
        {"header": "Titanio Ti (ppm)", "width": 14, "category": "aditivos"},
        {"header": "Vanadio V (ppm)", "width": 14, "category": "aditivos"},
        {"header": "Manganeso Mn (ppm)", "width": 16, "category": "aditivos"},
        {"header": "Fósforo P (ppm)", "width": 14, "category": "aditivos"},
        {"header": "Zinc Zn (ppm)", "width": 14, "category": "aditivos"},
        {"header": "Calcio Ca (ppm)", "width": 14, "category": "aditivos"},
        {"header": "Bario Ba (ppm)", "width": 14, "category": "aditivos"},
        {"header": "Cadmio Cd (ppm)", "width": 14, "category": "aditivos"},
        # Visual and notes
        {"header": "Apariencia Visual", "width": 20, "category": "otros"},
        {"header": "Comentarios", "width": 40, "category": "otros"},
        {"header": "Otros", "width": 30, "category": "otros"},
        {"header": "Recomendaciones", "width": 40, "category": "otros"},
        {"header": "Acción Requerida", "width": 40, "category": "otros"},
        {"header": "Tipo Muestreo", "width": 14, "category": "otros"},
        {"header": "Posición PM", "width": 14, "category": "otros"},
        {"header": "Horómetro Componente", "width": 18, "category": "otros"},
        {"header": "Horómetro Previo", "width": 16, "category": "otros"},
        {"header": "TR (días)", "width": 10, "category": "otros"},
    ]

    # Category colors for header grouping
    CATEGORY_COLORS: ClassVar[dict[str, str]] = {
        "id": "1F4E79",  # Dark blue
        "equipo": "2E75B6",  # Medium blue
        "lubricante": "5B9BD5",  # Light blue
        "fechas": "70AD47",  # Green
        "estado": "FFC000",  # Yellow/Orange
        "agua": "4472C4",  # Blue
        "viscosidad": "7030A0",  # Purple
        "acido_base": "C65911",  # Brown/Orange
        "ftir": "00B050",  # Green
        "particulas": "ED7D31",  # Orange
        "desgaste": "C00000",  # Red
        "contaminantes": "BF8F00",  # Dark yellow
        "aditivos": "548235",  # Dark green
        "otros": "7F7F7F",  # Gray
    }

    # Category group headers
    CATEGORY_HEADERS: ClassVar[dict[str, str]] = {
        "id": "IDENTIFICACIÓN",
        "equipo": "EQUIPO / COMPONENTE",
        "lubricante": "LUBRICANTE / USO",
        "fechas": "FECHAS",
        "estado": "ESTADO",
        "agua": "PRUEBAS DE AGUA",
        "viscosidad": "VISCOSIDAD",
        "acido_base": "ÁCIDO/BASE",
        "ftir": "ANÁLISIS FTIR",
        "particulas": "PARTÍCULAS",
        "desgaste": "METALES DE DESGASTE",
        "contaminantes": "CONTAMINANTES",
        "aditivos": "ADITIVOS",
        "otros": "OBSERVACIONES",
    }

    def __init__(
        self,
        queryset: QuerySet[models.Report],
    ) -> None:
        """
        Initialize the export service.

        Args:
            queryset: QuerySet of Report objects to export
        """
        self.queryset = queryset
        self.workbook: Workbook | None = None
        self.worksheet: Worksheet | None = None

    @property
    def effective_column_config(self) -> list[dict[str, Any]]:
        """
        Get the effective column configuration.

        Returns:
            List of column configuration dictionaries
        """
        return self.COLUMN_CONFIG

    def _create_styles(self) -> dict[str, Any]:
        """
        Create style definitions for the Excel file.

        Returns:
            Dictionary with style objects
        """
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )

        medium_border = Border(
            left=Side(style="medium", color="BFBFBF"),
            right=Side(style="medium", color="BFBFBF"),
            top=Side(style="medium", color="BFBFBF"),
            bottom=Side(style="medium", color="BFBFBF"),
        )

        return {
            "title_font": Font(bold=True, size=16, color="1F4E79"),
            "subtitle_font": Font(bold=True, size=11, color="404040"),
            "header_font": Font(bold=True, size=10, color="FFFFFF"),
            "category_header_font": Font(bold=True, size=9, color="FFFFFF"),
            "data_font": Font(size=9, color="333333"),
            "header_alignment": Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            ),
            "data_alignment": Alignment(
                horizontal="left",
                vertical="center",
                wrap_text=False,
            ),
            "number_alignment": Alignment(
                horizontal="right",
                vertical="center",
            ),
            "center_alignment": Alignment(
                horizontal="center",
                vertical="center",
            ),
            "thin_border": thin_border,
            "medium_border": medium_border,
            "alt_row_fill": PatternFill(
                start_color="F5F5F5",
                end_color="F5F5F5",
                fill_type="solid",
            ),
        }

    def _write_title_section(self, styles: dict[str, Any]) -> int:
        """
        Write the title section of the report.

        Args:
            styles: Dictionary with style objects

        Returns:
            Next row number to use
        """
        # Title
        self.worksheet.merge_cells("A1:G1")
        title_cell = self.worksheet["A1"]
        title_cell.value = _("REPORTE DE INSPECCIONES")
        title_cell.font = styles["title_font"]
        title_cell.alignment = Alignment(horizontal="left", vertical="center")
        self.worksheet.row_dimensions[1].height = 30

        # Empty row for spacing
        return 4

    def _write_category_headers(
        self,
        start_row: int,
        styles: dict[str, Any],
    ) -> int:
        """
        Write category group headers.

        Args:
            start_row: Row number to start writing
            styles: Dictionary with style objects

        Returns:
            Next row number to use
        """
        current_category = None
        category_start_col = 1
        col = 1

        for config in self.effective_column_config:
            category = config["category"]

            if current_category != category:
                if current_category is not None:
                    # Write previous category header
                    self._merge_category_header(
                        start_row,
                        category_start_col,
                        col - 1,
                        current_category,
                        styles,
                    )
                current_category = category
                category_start_col = col

            col += 1

        # Write last category header
        if current_category is not None:
            self._merge_category_header(
                start_row,
                category_start_col,
                col - 1,
                current_category,
                styles,
            )

        self.worksheet.row_dimensions[start_row].height = 22
        return start_row + 1

    def _merge_category_header(
        self,
        row: int,
        start_col: int,
        end_col: int,
        category: str,
        styles: dict[str, Any],
    ) -> None:
        """
        Merge cells and write a category header.

        Args:
            row: Row number
            start_col: Starting column
            end_col: Ending column
            category: Category key
            styles: Dictionary with style objects
        """
        if start_col < end_col:
            self.worksheet.merge_cells(
                start_row=row,
                start_column=start_col,
                end_row=row,
                end_column=end_col,
            )

        # Get the color for this category
        category_color = self.CATEGORY_COLORS.get(category, "808080")

        cell = self.worksheet.cell(row=row, column=start_col)
        cell.value = self.CATEGORY_HEADERS.get(category, category.upper())
        cell.font = styles["category_header_font"]
        cell.alignment = styles["header_alignment"]
        cell.fill = PatternFill(
            start_color=category_color,
            end_color=category_color,
            fill_type="solid",
        )
        cell.border = styles["medium_border"]

        # Apply fill to all merged cells (create new fill for each)
        for c in range(start_col + 1, end_col + 1):
            merge_cell = self.worksheet.cell(row=row, column=c)
            merge_cell.fill = PatternFill(
                start_color=category_color,
                end_color=category_color,
                fill_type="solid",
            )
            merge_cell.border = styles["medium_border"]

    def _write_column_headers(
        self,
        start_row: int,
        styles: dict[str, Any],
    ) -> int:
        """
        Write column headers.

        Args:
            start_row: Row number to start writing
            styles: Dictionary with style objects

        Returns:
            Next row number to use
        """
        for col, config in enumerate(self.effective_column_config, 1):
            cell = self.worksheet.cell(row=start_row, column=col)
            cell.value = config["header"]
            cell.font = styles["header_font"]
            cell.alignment = styles["header_alignment"]
            cell.border = styles["thin_border"]

            category = config["category"]
            # Use slightly lighter color for column headers
            cell.fill = PatternFill(
                start_color=self.CATEGORY_COLORS.get(category, "808080"),
                end_color=self.CATEGORY_COLORS.get(category, "808080"),
                fill_type="solid",
            )

            # Set column width
            col_letter = get_column_letter(col)
            self.worksheet.column_dimensions[col_letter].width = config["width"]

        self.worksheet.row_dimensions[start_row].height = 35
        return start_row + 1

    def _extract_report_data(self, report: models.Report, row_num: int) -> list[Any]:
        """
        Extract data from a report for a single row.

        Args:
            report: Report object to extract data from
            row_num: Row number (for numbering)

        Returns:
            List of values for the row
        """
        # Get related objects
        machine = report.machine
        component = report.component

        # Get analysis data if available
        analysis = getattr(report, "analysis", None)

        # Helper functions
        def format_date(date_val: Any) -> str:
            """Format date value to string."""
            if date_val:
                return date_val.strftime("%d/%m/%Y")
            return ""

        def safe_decimal(value: Any) -> Any:
            """Safely convert decimal to float for Excel."""
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return value
            return ""

        def safe_int(value: Any) -> Any:
            """Safely return integer or empty string."""
            if value is not None:
                return value
            return ""

        # Build row data matching effective column configuration
        row_data = [
            # Identification
            row_num,  # N°
            report.lab_number,  # No. Lab
            report.per_number or "",  # No. PER
            # Laboratory
            report.laboratory.name if report.laboratory else "",  # Laboratorio
        ]

        # Equipment
        row_data.extend(
            [
                machine.branch.name if machine and machine.branch else "",  # Cliente
                machine.name if machine else "",  # Equipo
                machine.model if machine else "",  # Modelo
                machine.serial_number if machine else "",  # No. Serie Equipo
                component.type.name
                if component and component.type
                else "",  # Componente
                report.serial_number_code or "",  # Cód/Núm Serie
                # Lubricant and usage
                report.lubricant or "",  # Lubricante
                safe_int(report.machine_hours),  # Equipo Horas
                safe_int(report.machine_kms),  # Equipo Kms
                safe_int(report.lubricant_hours),  # Lubricante Horas
                safe_int(report.lubricant_kms),  # Lubricante Kms
                # Dates
                format_date(report.sample_date),  # Fecha Muestra
                format_date(report.reception_date),  # Fecha Recepción
                format_date(report.report_date),  # Fecha Reporte
                # Status and condition
                report.get_status_display(),  # Estado
                report.get_condition_display(),  # Condición
                report.filter_change or "",  # Cambio Filtro
                report.oil_change or "",  # Cambio Aceite
            ]
        )

        # Analysis data
        if analysis:
            row_data.extend(
                [
                    # Water tests
                    analysis.water_crackle or "",
                    safe_decimal(analysis.water_distillation),
                    safe_decimal(analysis.refrigerant_pct),
                    # Viscosity
                    safe_decimal(analysis.viscosity_40c),
                    safe_decimal(analysis.viscosity_100c),
                    safe_int(analysis.viscosity_index),
                    # Acid/Base numbers
                    analysis.compatibility or "",
                    safe_decimal(analysis.tbn),
                    safe_decimal(analysis.tan),
                    # FTIR Analysis
                    safe_decimal(analysis.oxidation),
                    safe_decimal(analysis.soot),
                    safe_decimal(analysis.nitration),
                    safe_decimal(analysis.sulfation),
                    safe_decimal(analysis.glycol),
                    safe_decimal(analysis.fuel_dilution),
                    safe_decimal(analysis.water_ftir),
                    # Particle analysis
                    safe_int(analysis.pq_index),
                    analysis.particle_count_iso or "",
                    safe_int(analysis.particle_4um),
                    safe_int(analysis.particle_6um),
                    safe_int(analysis.particle_14um),
                    safe_int(analysis.particle_21um),
                    safe_int(analysis.particle_38um),
                    safe_int(analysis.particle_70um),
                    # Wear metals
                    safe_int(analysis.iron_fe),
                    safe_int(analysis.chromium_cr),
                    safe_int(analysis.lead_pb),
                    safe_int(analysis.copper_cu),
                    safe_int(analysis.tin_sn),
                    safe_int(analysis.aluminum_al),
                    safe_int(analysis.nickel_ni),
                    safe_int(analysis.silver_ag),
                    # Contaminants
                    safe_int(analysis.silicon_si),
                    safe_int(analysis.boron_b),
                    safe_int(analysis.sodium_na),
                    safe_int(analysis.potassium_k),
                    analysis.dispersancy or "",
                    analysis.spot_test or "",
                    # Additives
                    safe_int(analysis.magnesium_mg),
                    safe_int(analysis.molybdenum_mo),
                    safe_int(analysis.titanium_ti),
                    safe_int(analysis.vanadium_v),
                    safe_int(analysis.manganese_mn),
                    safe_int(analysis.phosphorus_p),
                    safe_int(analysis.zinc_zn),
                    safe_int(analysis.calcium_ca),
                    safe_int(analysis.barium_ba),
                    safe_int(analysis.cadmium_cd),
                    # Visual and notes
                    analysis.visual_appearance or "",
                ]
            )
        else:
            # Fill with empty values for analysis columns (49 columns)
            row_data.extend([""] * 49)

        # Notes and others (report-level fields)
        row_data.extend(
            [
                report.notes or "",  # Comentarios
                report.others or "",  # Otros
                report.recommendations or "",  # Recomendaciones
                report.action_required or "",  # Acción Requerida
                report.sampling_type or "",  # Tipo Muestreo
                report.pm_position or "",  # Posición PM
                safe_int(report.component_hour_meter),  # Horómetro Componente
                safe_int(report.previous_hour_meter),  # Horómetro Previo
                safe_int(report.turnaround_days),  # TR (días)
            ]
        )

        return row_data

    def _write_data_rows(
        self,
        start_row: int,
        styles: dict[str, Any],
    ) -> int:
        """
        Write data rows from the queryset.

        Args:
            start_row: Row number to start writing
            styles: Dictionary with style objects

        Returns:
            Next row number to use
        """
        # Optimize queryset with related objects
        reports = self.queryset.select_related(
            "laboratory",
            "machine",
            "machine__branch",
            "component",
            "component__type",
            "analysis",
        )

        current_row = start_row
        for idx, report in enumerate(reports, 1):
            row_data = self._extract_report_data(report, idx)

            for col, value in enumerate(row_data, 1):
                cell = self.worksheet.cell(row=current_row, column=col)
                cell.value = value
                cell.font = styles["data_font"]
                cell.border = styles["thin_border"]

                # Apply alignment based on value type
                if isinstance(value, (int, float)) and value != "":
                    cell.alignment = styles["number_alignment"]
                elif col <= 3:  # ID columns centered
                    cell.alignment = styles["center_alignment"]
                else:
                    cell.alignment = styles["data_alignment"]

            # Apply alternating row colors
            if idx % 2 == 0:
                for col in range(1, len(row_data) + 1):
                    self.worksheet.cell(row=current_row, column=col).fill = styles[
                        "alt_row_fill"
                    ]

            current_row += 1

        return current_row

    def _apply_conditional_formatting(self) -> None:
        """Apply conditional formatting for condition column."""
        # Find condition column index
        condition_col = None
        for idx, config in enumerate(self.effective_column_config, 1):
            if config["header"] == "Condición":
                condition_col = idx
                break

        if condition_col is None:
            return

        # Condition color mapping
        condition_colors = {
            "Normal": "C6EFCE",  # Light green
            "Precaución": "FFEB9C",  # Light yellow
            "Crítico": "FFC7CE",  # Light red
        }

        # Apply colors to condition cells
        for row in range(6, self.worksheet.max_row + 1):
            cell = self.worksheet.cell(row=row, column=condition_col)
            condition = str(cell.value) if cell.value else ""

            for cond_text, color in condition_colors.items():
                if cond_text.lower() in condition.lower():
                    cell.fill = PatternFill(
                        start_color=color,
                        end_color=color,
                        fill_type="solid",
                    )
                    break

    def _freeze_panes(self) -> None:
        """Freeze header rows and first columns."""
        # Freeze after row 5 (title + category headers + column headers)
        # and after column C (first 3 ID columns)
        self.worksheet.freeze_panes = "D6"

    def generate_export(self) -> BytesIO:
        """
        Generate the Excel export file.

        Returns:
            BytesIO buffer containing the Excel file
        """
        self.workbook = Workbook()
        self.worksheet = self.workbook.active

        # Set worksheet title
        title = "Reportes de Inspección"
        self.worksheet.title = title

        # Create styles
        styles = self._create_styles()

        # Write sections
        next_row = self._write_title_section(styles)
        next_row = self._write_category_headers(next_row, styles)
        next_row = self._write_column_headers(next_row, styles)
        self._write_data_rows(next_row, styles)

        # Apply formatting
        self._apply_conditional_formatting()
        self._freeze_panes()

        # Save to buffer
        buffer = BytesIO()
        self.workbook.save(buffer)
        buffer.seek(0)

        return buffer

    def get_filename(self) -> str:
        """
        Generate the export filename.

        Returns:
            Filename string with timestamp
        """
        current_time = timezone.now().strftime("%Y%m%d_%H%M%S")
        return f"reportes_inspeccion_{current_time}.xlsx"

    def build_preview(self, limit: int = 20) -> dict[str, Any]:
        """
        Build a JSON-serializable preview of the export data.

        Args:
            limit: Maximum number of rows to include in the preview.

        Returns:
            Dictionary with the column headers and the preview rows.
        """
        headers = [config["header"] for config in self.effective_column_config]
        reports = self.queryset.select_related(
            "laboratory",
            "machine",
            "machine__branch",
            "component",
            "component__type",
            "analysis",
        )[:limit]
        rows = [
            self._extract_report_data(report, index)
            for index, report in enumerate(reports, 1)
        ]
        return {"columns": headers, "rows": rows}

    @classmethod
    def preview(
        cls, queryset: QuerySet[models.Report], limit: int = 20
    ) -> dict[str, Any]:
        """
        Class method to build an export preview for a queryset.

        Args:
            queryset: QuerySet of Report objects to preview.
            limit: Maximum number of rows to include in the preview.

        Returns:
            Dictionary with the column headers and the preview rows.
        """
        service = cls(queryset=queryset)
        return service.build_preview(limit=limit)

    @classmethod
    def export_to_response(
        cls, queryset: QuerySet[models.Report]
    ) -> tuple[BytesIO, str]:
        """
        Class method to generate export and return buffer with filename.

        Args:
            queryset: QuerySet of Report objects to export

        Returns:
            Tuple of (BytesIO buffer, filename string)
        """
        service = cls(
            queryset=queryset,
        )
        buffer = service.generate_export()
        filename = service.get_filename()
        return buffer, filename
