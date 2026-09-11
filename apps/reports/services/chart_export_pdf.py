import base64
import io
import logging
from typing import Any, Dict, List, Optional

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


class ChartExportPDFService:
    """Service for generating component analysis PDF reports.

    Handles the creation of PDF documents containing chart images,
    summary data, and wear source information.
    """

    CHART_TITLES: List[str] = [
        _("Wear Metals Profile (Fe, Cu, Al, Pb, Cr, Si, K)"),
        _("Wear Trends (Fe, Cu, Al)"),
        _("Contamination Alerts (Si, Na, K)"),
        _("Oil Health (Si, Na, K, Viscosity, Lubricant)"),
        _("Additive Elements (Zn, P, Mg, Ca)"),
        _("Usage vs Wear Correlation"),
    ]

    PARAM_LABELS: Dict[str, str] = {
        "iron_fe": str(_("Iron (Fe)")),
        "copper_cu": str(_("Copper (Cu)")),
        "aluminum_al": str(_("Aluminum (Al)")),
        "silicon_si": str(_("Silicon (Si)")),
        "potassium_k": str(_("Potassium (K)")),
        "lead_pb": str(_("Lead (Pb)")),
        "chromium_cr": str(_("Chromium (Cr)")),
    }

    def __init__(
        self,
        charts: List[str],
        summary: Dict[str, Any],
        organization_name: Optional[str] = None,
    ) -> None:
        """Initialize service with chart and summary data.

        Args:
            charts: List of base64-encoded chart image strings.
            summary: Dictionary with component summary data.
            organization_name: Optional organization name for the footer.
        """
        self.charts = charts
        self.summary = summary
        self.organization_name = organization_name
        self._styles: Dict[str, ParagraphStyle] = {}
        self._init_styles()

    def _init_styles(self) -> None:
        """Initialize PDF paragraph styles."""
        base_styles = getSampleStyleSheet()

        self._styles["title"] = ParagraphStyle(
            "CustomTitle",
            parent=base_styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1E1E2D"),
            spaceAfter=30,
            alignment=1,
        )
        self._styles["subtitle"] = ParagraphStyle(
            "CustomSubtitle",
            parent=base_styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#3F4254"),
            spaceAfter=20,
        )
        self._styles["normal"] = ParagraphStyle(
            "CustomNormal",
            parent=base_styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#5E6278"),
        )
        self._styles["wear_header"] = ParagraphStyle(
            "WearSourceHeader",
            parent=base_styles["Heading3"],
            fontSize=12,
            textColor=colors.HexColor("#1E1E2D"),
            spaceAfter=5,
        )
        self._styles["wear_subtitle"] = ParagraphStyle(
            "WearSourceSubtitle",
            parent=base_styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#7E8299"),
            spaceAfter=15,
        )
        self._styles["wear_label"] = ParagraphStyle(
            "WearSourceLabel",
            parent=base_styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#1E1E2D"),
            fontName="Helvetica-Bold",
        )
        self._styles["wear_desc"] = ParagraphStyle(
            "WearSourceDesc",
            parent=base_styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#5E6278"),
            leftIndent=15,
            spaceBefore=2,
            spaceAfter=8,
        )

    def generate(self) -> HttpResponse:
        """Generate the PDF and return it as an HttpResponse.

        Returns:
            HttpResponse with PDF content and appropriate headers.

        Raises:
            ValueError: If no chart data is provided.
        """
        if not self.charts:
            raise ValueError("No charts data provided")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        elements = self._build_elements(doc)
        doc.build(
            elements,
            onFirstPage=self._add_footer,
            onLaterPages=self._add_footer,
        )

        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{self._get_filename()}"'
        )
        return response

    def _build_elements(self, doc: SimpleDocTemplate) -> List[Any]:
        """Build the list of PDF flowable elements.

        Args:
            doc: The SimpleDocTemplate used for layout dimensions.

        Returns:
            List of reportlab flowable elements.
        """
        elements: List[Any] = []

        # Title
        elements.append(
            Paragraph(
                str(_("Component Analysis Report")),
                self._styles["title"],
            )
        )

        # Summary table
        elements.append(self._build_summary_table())
        elements.append(Spacer(1, 0.15 * inch))

        # First chart with wear sources sidebar
        first_section = self._build_first_chart_section(doc)
        if first_section:
            elements.append(first_section)

        # Page break after first section if more charts exist
        if len(self.charts) > 1:
            elements.append(PageBreak())

        # Remaining charts (full-width, one per page)
        elements.extend(self._build_remaining_chart_sections(doc))

        return elements

    def _build_summary_table(self) -> Table:
        """Build the summary information table.

        Returns:
            A Table flowable with component summary data.
        """
        normal = self._styles["normal"]
        summary_data = [
            [
                Paragraph(f"<b>{_('Component Type')}:</b>", normal),
                Paragraph(self.summary.get("component_type", "N/A"), normal),
                Paragraph(f"<b>{_('Machine')}:</b>", normal),
                Paragraph(self.summary.get("machine_name", "N/A"), normal),
            ],
            [
                Paragraph(f"<b>{_('Last Sample')}:</b>", normal),
                Paragraph(self.summary.get("latest_sample_date", "N/A"), normal),
                Paragraph(f"<b>{_('Total Reports')}:</b>", normal),
                Paragraph(str(self.summary.get("total_reports", "0")), normal),
            ],
        ]

        table = Table(
            summary_data,
            colWidths=[1.5 * inch, 2.5 * inch, 1.5 * inch, 2.5 * inch],
        )
        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#F5F8FA"),
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#E4E6EF"),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return table

    def _decode_chart_image(self, chart_data: str) -> Image:
        """Decode a base64-encoded chart image into a reportlab Image.

        Args:
            chart_data: Base64-encoded image string, optionally with data URL prefix.

        Returns:
            A reportlab Image object.
        """
        if "," in chart_data:
            chart_data = chart_data.split(",")[1]

        img_data = base64.b64decode(chart_data)
        img_buffer = io.BytesIO(img_data)
        return Image(img_buffer)

    def _scale_image(
        self,
        img: Image,
        max_width: float,
        max_height: float,
    ) -> Image:
        """Scale an image to fit within the given dimensions while preserving aspect ratio.

        Args:
            img: The reportlab Image to scale.
            max_width: Maximum allowed width in points.
            max_height: Maximum allowed height in points.

        Returns:
            The same Image with updated draw dimensions.
        """
        aspect = img.imageHeight / float(img.imageWidth)

        if img.imageWidth > max_width:
            img.drawWidth = max_width
            img.drawHeight = max_width * aspect
        else:
            img.drawWidth = img.imageWidth
            img.drawHeight = img.imageHeight

        if img.drawHeight > max_height:
            img.drawHeight = max_height
            img.drawWidth = max_height / aspect

        return img

    def _build_wear_sources_column(self, width: float) -> Table:
        """Build the wear sources sidebar for the first chart section.

        Args:
            width: Available width for the column in points.

        Returns:
            A Table flowable containing wear source information.
        """
        wear_sources_data: Dict[str, str] = self.summary.get("wear_sources", {})
        elements: List[Any] = []

        if wear_sources_data:
            elements.append(
                Paragraph(
                    str(_("Wear Sources")),
                    self._styles["wear_header"],
                )
            )
            elements.append(
                Paragraph(
                    str(_("Possible origins of detected wear")),
                    self._styles["wear_subtitle"],
                )
            )

            for param_key, description in wear_sources_data.items():
                label = self.PARAM_LABELS.get(param_key, param_key)
                elements.append(
                    Paragraph(
                        f"\u2022 <b>{label}:</b>",
                        self._styles["wear_label"],
                    )
                )
                elements.append(Paragraph(description, self._styles["wear_desc"]))
        else:
            elements.append(
                Paragraph(
                    str(_("No wear source information available")),
                    self._styles["normal"],
                )
            )

        table = Table(
            [[elem] for elem in elements],
            colWidths=[width - 0.3 * inch],
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#F5F8FA"),
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#E4E6EF"),
                    ),
                ]
            )
        )
        return table

    def _build_first_chart_section(
        self, doc: SimpleDocTemplate
    ) -> Optional[KeepTogether]:
        """Build the first chart section with a two-column layout.

        The left column contains the radar chart and the right column
        displays wear source descriptions.

        Args:
            doc: The SimpleDocTemplate used for layout dimensions.

        Returns:
            A KeepTogether flowable or None if the chart cannot be processed.
        """
        if not self.charts:
            return None

        try:
            img = self._decode_chart_image(self.charts[0])

            left_col_width = doc.width * 0.60
            right_col_width = doc.width * 0.40
            chart_height = 3.8 * inch

            img = self._scale_image(img, left_col_width, chart_height)

            right_col_table = self._build_wear_sources_column(right_col_width)

            two_col_table = Table(
                [[img, right_col_table]],
                colWidths=[left_col_width, right_col_width],
                hAlign="LEFT",
            )
            two_col_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (0, 0), 0),
                        ("RIGHTPADDING", (0, 0), (0, 0), 10),
                        ("LEFTPADDING", (1, 0), (1, 0), 10),
                        ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ]
                )
            )

            chart_title = Paragraph(
                str(self.CHART_TITLES[0]),
                self._styles["subtitle"],
            )

            return KeepTogether(
                [
                    chart_title,
                    Spacer(1, 0.1 * inch),
                    two_col_table,
                ]
            )

        except Exception:
            logger.exception("Error building first chart section")
            return None

    def _build_remaining_chart_sections(self, doc: SimpleDocTemplate) -> List[Any]:
        """Build full-width sections for charts after the first one.

        Args:
            doc: The SimpleDocTemplate used for layout dimensions.

        Returns:
            List of flowable elements for the remaining charts.
        """
        elements: List[Any] = []
        available_width = doc.width
        available_height = 3.5 * inch

        for i, chart_data in enumerate(self.charts[1:], start=1):
            if i >= len(self.CHART_TITLES):
                break

            elements.append(
                Paragraph(
                    str(self.CHART_TITLES[i]),
                    self._styles["subtitle"],
                )
            )

            try:
                img = self._decode_chart_image(chart_data)
                img = self._scale_image(img, available_width, available_height)
                elements.append(img)
                elements.append(Spacer(1, 0.2 * inch))
            except Exception:
                logger.exception(f"Error loading chart at index {i}")
                elements.append(
                    Paragraph(
                        f"Error loading chart {i}",
                        self._styles["normal"],
                    )
                )

            if i < len(self.charts) - 1:
                elements.append(PageBreak())

        return elements

    def _add_footer(self, canvas_obj: Any, doc_obj: Any) -> None:
        """Add footer to each page of the PDF.

        Args:
            canvas_obj: The reportlab canvas object.
            doc_obj: The document template object.
        """
        canvas_obj.saveState()
        footer_text = (
            f"{_('Generated on')}: {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        )
        if self.organization_name:
            footer_text += f" | {self.organization_name}"

        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor("#7E8299"))
        canvas_obj.drawCentredString(
            doc_obj.pagesize[0] / 2.0,
            0.5 * inch,
            footer_text,
        )
        canvas_obj.restoreState()

    def _get_filename(self) -> str:
        """Generate the PDF filename.

        Returns:
            A formatted filename string.
        """
        current_time = timezone.now().strftime("%Y%m%d_%H%M%S")
        component_type = self.summary.get("component_type", "component")
        return f"analisis_{component_type}_{current_time}.pdf"
