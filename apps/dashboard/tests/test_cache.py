"""Tests for the ``apps.dashboard.cache`` helpers."""

from django.core.cache import cache
from django.test import TestCase

from apps.dashboard import cache as dashboard_cache


class DashboardCacheTests(TestCase):
    """Tests for the dashboard cache version helpers."""

    def setUp(self) -> None:
        cache.clear()

    def tearDown(self) -> None:
        cache.clear()

    def test_get_cache_version_defaults(self) -> None:
        """Without a stored version the default is returned."""
        self.assertEqual(
            dashboard_cache.get_cache_version(), dashboard_cache.DEFAULT_VERSION
        )

    def test_bump_cache_version_starts_after_default(self) -> None:
        """The first bump stores the default version plus one."""
        self.assertEqual(dashboard_cache.bump_cache_version(), 2)
        self.assertEqual(dashboard_cache.get_cache_version(), 2)

    def test_bump_cache_version_increments(self) -> None:
        """Consecutive bumps keep increasing the version."""
        dashboard_cache.bump_cache_version()
        self.assertEqual(dashboard_cache.bump_cache_version(), 3)

    def test_build_payload_key_includes_version_and_filters(self) -> None:
        """The payload key combines the version with the filter signature."""
        dashboard_cache.bump_cache_version()
        key = dashboard_cache.build_payload_key("2024:1:2:3")
        self.assertIn("2024:1:2:3", key)
        self.assertTrue(key.startswith(f"{dashboard_cache.CACHE_KEY_PREFIX}:2:"))
