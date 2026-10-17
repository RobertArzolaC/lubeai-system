"""Tests for the laboratory feature flag."""

from constance import config
from constance.test import override_config
from django.test import TestCase


class LaboratoryFeatureFlagTests(TestCase):
    """``ENABLE_LABS`` controls laboratory visibility across the UI."""

    def test_defaults_to_false(self) -> None:
        """Laboratories are hidden by default."""
        self.assertFalse(config.ENABLE_LABS)

    @override_config(ENABLE_LABS=True)
    def test_can_be_enabled(self) -> None:
        """The flag can be turned on."""
        self.assertTrue(config.ENABLE_LABS)
