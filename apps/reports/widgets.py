"""Form widgets used by the reports app."""

from pathlib import Path
from typing import Any

from django import forms


class ReportPDFInput(forms.ClearableFileInput):
    """File input that shows the stored PDF name without linking to MEDIA_URL."""

    template_name = "reports/widgets/report_pdf_input.html"

    def get_context(
        self, name: str, value: Any, attrs: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Add the plain filename to the widget context.

        Args:
            name: Field name.
            value: Current field value.
            attrs: Widget attributes.

        Returns:
            The widget context with a ``filename`` entry.
        """
        context = super().get_context(name, value, attrs)
        context["widget"]["filename"] = Path(value.name).name if value else ""
        return context
