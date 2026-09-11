"""Template content tests for the dashboard app."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates" / "dashboard"
INDEX = TEMPLATE_DIR / "index.html"


class DashboardTemplateContentTests(SimpleTestCase):
    """Static checks on the dashboard template files."""

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_index_embeds_dashboard_data(self) -> None:
        """The index embeds the payload and loads the charts script."""
        content = self._read(INDEX)
        self.assertIn("dashboard-data", content)
        self.assertIn("js/dashboard.js", content)
        self.assertIn("apexcharts.min.js", content)

    def test_kpis_include_expected_labels(self) -> None:
        """KPI cards expose the expected (English msgid) labels."""
        content = self._read(TEMPLATE_DIR / "includes" / "kpis.html")
        for label in ("Total Samples", "Normal", "Precaution", "Non-Conformance Rate"):
            self.assertIn(label, content)

    def test_placeholder_data_removed(self) -> None:
        """The old hardcoded placeholder values are gone."""
        content = self._read(INDEX)
        for value in ("$3.456K", "45.2K", "Total Profit", "Welcome back"):
            self.assertNotIn(value, content)

    def test_tabs_are_present(self) -> None:
        """Only the summary and data table tabs are rendered."""
        content = self._read(TEMPLATE_DIR / "includes" / "tabs.html")
        for label in ("Summary", "Data Table"):
            self.assertIn(label, content)
        for label in ("Trends", "Wear", "Contamination", "Oil Health", "References"):
            self.assertNotIn(label, content)
