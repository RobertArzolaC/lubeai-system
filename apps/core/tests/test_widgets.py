"""Tests for the custom DAL Select2 widgets in ``apps.core.widgets``."""

from django.test import SimpleTestCase, override_settings

from apps.core.widgets import ThemeModelSelect2


@override_settings(DEBUG=True)
class ThemeModelSelect2DebugMediaTests(SimpleTestCase):
    """Widget media in debug mode uses non-minified assets."""

    def setUp(self) -> None:
        self.widget = ThemeModelSelect2(url="apps.core:autocomplete_country")

    def test_widget_is_flagged_as_select2(self) -> None:
        """The widget exposes an ``is_select2`` flag for templates."""
        self.assertTrue(self.widget.is_select2)

    def test_media_includes_vendored_jquery_and_select2(self) -> None:
        """Django admin's vendored jQuery and Select2 are part of the media."""
        media = str(self.widget.media)
        self.assertIn("admin/js/vendor/jquery/jquery.min.js", media)
        self.assertIn("admin/js/vendor/select2/select2.full.js", media)
        self.assertIn("admin/css/vendor/select2/select2.css", media)

    def test_media_includes_dal_glue(self) -> None:
        """The DAL autocomplete glue scripts are part of the media."""
        media = str(self.widget.media)
        self.assertIn("autocomplete_light/autocomplete_light.js", media)
        self.assertIn("autocomplete_light/select2.js", media)


@override_settings(DEBUG=False)
class ThemeModelSelect2ProductionMediaTests(SimpleTestCase):
    """Widget media outside debug mode uses minified assets."""

    def setUp(self) -> None:
        self.widget = ThemeModelSelect2(url="apps.core:autocomplete_country")

    def test_media_uses_minified_assets(self) -> None:
        """Minified jQuery, Select2 and DAL assets are used."""
        media = str(self.widget.media)
        self.assertIn("admin/js/vendor/jquery/jquery.min.js", media)
        self.assertIn("admin/js/vendor/select2/select2.full.min.js", media)
        self.assertIn("admin/css/vendor/select2/select2.min.css", media)
        self.assertIn("autocomplete_light/autocomplete_light.min.js", media)
        self.assertIn("autocomplete_light/select2.min.js", media)
