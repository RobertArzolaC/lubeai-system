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

    def test_filters_expose_the_search_box(self) -> None:
        """The filter bar offers a free-text search next to the selects."""
        content = self._read(TEMPLATE_DIR / "includes" / "filters.html")
        self.assertIn('name="search"', content)
        self.assertIn('type="search"', content)

    def test_filters_render_autocomplete_fields(self) -> None:
        """Machine and component use the server-side autocomplete widgets."""
        content = self._read(TEMPLATE_DIR / "includes" / "filters.html")
        self.assertIn("filter_form.machine", content)
        self.assertIn("filter_form.component", content)
        self.assertNotIn('name="component_type"', content)

    def test_filters_share_a_single_control_style(self) -> None:
        """Every static filter control uses the shared ``filter-control`` class."""
        content = self._read(TEMPLATE_DIR / "includes" / "filters.html")
        self.assertEqual(content.count('class="filter-control w-full"'), 3)

    def test_index_loads_select2_assets(self) -> None:
        """The index loads the widget media and the custom Select2 skins."""
        content = self._read(INDEX)
        self.assertIn("filter_form.media", content)
        self.assertIn("select2-custom.css", content)
        self.assertIn("dashboard-filters.css", content)

    def test_filter_bar_styles_match_native_and_select2_controls(self) -> None:
        """The filter stylesheet normalises native controls and Select2 widgets."""
        content = (
            Path(settings.BASE_DIR) / "static" / "css" / "dashboard-filters.css"
        ).read_text(encoding="utf-8")
        self.assertIn("#dashboard-filters .filter-control", content)
        self.assertIn(
            "#dashboard-filters .select2-container--default .select2-selection--single",
            content,
        )
        self.assertIn(
            "body .select2-container--default .select2-search--dropdown .select2-search__field",
            content,
        )
