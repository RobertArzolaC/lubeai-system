"""Tests for apps.dashboard.views."""

from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.dashboard.services.dashboard_service import DashboardService
from apps.equipment import factories as equipment_factories
from apps.reports import factories as reports_factories
from apps.users import factories as users_factories

DASHBOARD_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [settings.BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"dashboard/index.html": "{{ dashboard_data }}"},
                ),
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "constance.context_processors.config",
                "apps.core.context_processors.site_processor",
            ],
        },
    }
]


@override_settings(TEMPLATES=DASHBOARD_TEMPLATES)
class DashboardViewTests(TestCase):
    """Tests for the dashboard page and data endpoint."""

    def setUp(self) -> None:
        cache.clear()
        self.user = users_factories.UserFactory()
        self.machine = equipment_factories.MachineFactory(name="Buque Test")
        reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 3, 1)
        )
        reports_factories.ReportFactory(
            machine=self.machine, condition="CRITICAL", sample_date=date(2024, 4, 1)
        )

    def tearDown(self) -> None:
        cache.clear()

    def test_index_requires_login(self) -> None:
        """Anonymous users are redirected to login."""
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 302)

    def test_index_renders_for_logged_user(self) -> None:
        """Logged-in users can render the dashboard shell."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index.html")
        self.assertIn("dashboard_data", response.context)
        self.assertIn("filter_options", response.context)

    def test_data_requires_login(self) -> None:
        """The JSON endpoint requires authentication."""
        response = self.client.get(reverse("apps.dashboard:data"))
        self.assertEqual(response.status_code, 302)

    def test_data_returns_expected_contract(self) -> None:
        """The JSON endpoint returns the dashboard payload."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:data"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in (
            "kpis",
            "condition_distribution",
            "samples_by_month",
            "alerts_by_fleet",
            "alerts_over_time",
            "iso4406",
            "range",
            "recent_reports",
            "total",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["kpis"]["total"], 2)

    def test_data_applies_year_filter(self) -> None:
        """The JSON endpoint respects the year filter."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:data"), {"year": 2024})
        self.assertEqual(response.json()["kpis"]["total"], 2)
        response = self.client.get(reverse("apps.dashboard:data"), {"year": 2023})
        self.assertEqual(response.json()["kpis"]["total"], 0)

    def test_data_handles_invalid_filter(self) -> None:
        """An invalid filter value returns HTTP 400."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.dashboard:data"), {"year": "abc"})
        self.assertEqual(response.status_code, 400)

    def test_data_query_count_is_bounded(self) -> None:
        """The endpoint avoids N+1 queries as the dataset grows."""
        for month in range(1, 6):
            reports_factories.ReportFactory(
                machine=self.machine,
                condition="NORMAL",
                sample_date=date(2024, month, 15),
            )
        self.client.force_login(self.user)
        DashboardService()  # warm up any lazy imports
        with self.assertNumQueries(13):
            self.client.get(reverse("apps.dashboard:data"))

    def _query_count(self, path: str, **params: object) -> int:
        """Return the number of SQL queries executed for a request."""
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(path, params)
        return len(ctx.captured_queries)

    def test_data_payload_is_cached_between_requests(self) -> None:
        """A second identical request is served from the cache."""
        self.client.force_login(self.user)
        first = self._query_count(reverse("apps.dashboard:data"))
        second = self._query_count(reverse("apps.dashboard:data"))
        self.assertLess(second, first)

    def test_cache_invalidated_when_report_saved(self) -> None:
        """Saving a new report invalidates the cached payload."""
        self.client.force_login(self.user)
        first = self.client.get(reverse("apps.dashboard:data")).json()
        self.assertEqual(first["kpis"]["total"], 2)

        reports_factories.ReportFactory(
            machine=self.machine, condition="NORMAL", sample_date=date(2024, 5, 1)
        )

        second = self.client.get(reverse("apps.dashboard:data")).json()
        self.assertEqual(second["kpis"]["total"], 3)


class DashboardRealTemplateSmokeTests(TestCase):
    """Render the real dashboard template with the default template engine."""

    def setUp(self) -> None:
        """Avoid leaking cached dashboard pages across tests."""
        cache.clear()

    def tearDown(self) -> None:
        """Drop any cached dashboard page produced by the view."""
        cache.clear()

    def test_index_renders_real_template(self) -> None:
        """A logged-in user gets the full dashboard shell from the real engine."""
        user = users_factories.UserFactory()
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("dashboard-data", content)
        self.assertIn("apexcharts.min.js", content)
        self.assertIn("Total Muestras", content)
