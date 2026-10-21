"""Placeholder PDF generation for reports without a document."""

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_dummy_report_pdf(lab_number: str) -> bytes:
    """Return a minimal PDF that marks the report as a placeholder.

    Args:
        lab_number: Laboratory report number printed in the document.

    Returns:
        The generated PDF bytes.
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, height - 100, "DOCUMENTO DE EJEMPLO")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(72, height - 140, f"Informe: {lab_number}")
    pdf.drawString(
        72,
        height - 170,
        "Este PDF es un marcador de posición generado automáticamente.",
    )
    pdf.drawString(72, height - 190, "Reemplácelo por el documento real.")
    pdf.save()
    return buffer.getvalue()
