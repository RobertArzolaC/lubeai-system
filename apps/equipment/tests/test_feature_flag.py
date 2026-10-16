"""Tests for the fleet feature flag."""

from constance import config
from constance.test import override_config
from django.test import TestCase


class FleetFeatureFlagTests(TestCase):
    """``ENABLE_FLEET`` controls fleet visibility across the UI."""

    def test_defaults_to_false(self) -> None:
        """Fleet is hidden by default."""
        self.assertFalse(config.ENABLE_FLEET)

    @override_config(ENABLE_FLEET=True)
    def test_can_be_enabled(self) -> None:
        """The flag can be turned on."""
        self.assertTrue(config.ENABLE_FLEET)
