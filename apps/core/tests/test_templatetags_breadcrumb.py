"""Tests for the ``apps.core.templatetags.breadcrumb_tags`` tag."""

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core.templatetags.breadcrumb_tags import breadcrumb


class BreadcrumbTests(TestCase):
    """Tests for the ``breadcrumb`` template tag."""

    def _titles(self, path: str) -> list[str]:
        """Return the translated breadcrumb titles for ``path``."""
        request = RequestFactory().get(path)
        crumbs = breadcrumb({"request": request})
        return [str(crumb["title"]) for crumb in crumbs]

    def test_dashboard_path_marks_dashboard_active(self) -> None:
        """On the dashboard the first crumb is marked as active."""
        request = RequestFactory().get(reverse("apps.dashboard:index"))
        crumbs = breadcrumb({"request": request})
        self.assertEqual(len(crumbs), 1)
        self.assertEqual(crumbs[0]["url"], "/dashboard/")
        self.assertTrue(crumbs[0]["is_active"])

    def test_reports_list(self) -> None:
        """The reports list shows the reports entity."""
        self.assertEqual(
            self._titles(reverse("apps.reports:report_list")),
            ["Tablero", "Informes"],
        )

    def test_report_detail_includes_parent_list(self) -> None:
        """A nested detail page includes the parent list crumb."""
        path = reverse("apps.reports:report_detail", kwargs={"pk": 1})
        self.assertEqual(self._titles(path), ["Tablero", "Informes", "Detalle"])

    def test_analysis_threshold_list(self) -> None:
        """The thresholds list uses its translated label."""
        path = reverse("apps.reports:analysisthreshold_list")
        self.assertEqual(self._titles(path), ["Tablero", "Informes", "Umbrales"])

    def test_component_analysis(self) -> None:
        """The component analysis page uses its translated label."""
        path = reverse("apps.reports:component_analysis")
        self.assertEqual(
            self._titles(path), ["Tablero", "Informes", "Análisis de componente"]
        )

    def test_report_export(self) -> None:
        """The export page renders a translated action label."""
        path = reverse("apps.reports:report_export")
        self.assertEqual(self._titles(path), ["Tablero", "Informes", "Exportar"])

    def test_branch_list(self) -> None:
        """Equipment list pages use the sidebar translations."""
        path = reverse("apps.equipment:branch_list")
        self.assertEqual(self._titles(path), ["Tablero", "Sucursales"])

    def test_component_type_detail_multiword_entity(self) -> None:
        """Multi-word entities keep the entity name and append the action."""
        path = reverse("apps.equipment:component_type_detail", kwargs={"pk": 1})
        self.assertEqual(
            self._titles(path), ["Tablero", "Tipos de componente", "Detalle"]
        )

    def test_machine_update_trail(self) -> None:
        """An update page shows list, detail and the update action."""
        path = reverse("apps.equipment:machine_update", kwargs={"pk": 1})
        self.assertEqual(
            self._titles(path),
            ["Tablero", "Máquinas", "Detalle", "Actualizar"],
        )

    def test_alert_list(self) -> None:
        """Alerts list uses its translated label."""
        path = reverse("apps.alerts:alert_list")
        self.assertEqual(self._titles(path), ["Tablero", "Alertas"])

    def test_account_list(self) -> None:
        """Accounts list uses its translated label."""
        path = reverse("apps.users:account_list")
        self.assertEqual(self._titles(path), ["Tablero", "Cuentas"])

    def test_account_update_trail(self) -> None:
        """The account update URL (action before pk) resolves the action."""
        path = reverse("apps.users:account_update", kwargs={"pk": 1})
        self.assertEqual(self._titles(path), ["Tablero", "Cuentas", "Actualizar"])

    def test_profile(self) -> None:
        """Standalone pages use their special label."""
        path = reverse("apps.users:profile")
        self.assertEqual(self._titles(path), ["Tablero", "Perfil"])

    def test_unknown_path_keeps_dashboard_crumb(self) -> None:
        """Unresolvable path segments are skipped gracefully."""
        self.assertEqual(self._titles("/no/such/route/"), ["Tablero"])
