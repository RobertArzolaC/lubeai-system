"""DAL Select2 widgets wired to Django's vendored jQuery and Select2 assets.

The theme does not ship a JavaScript bundle that provides jQuery and Select2,
so the widgets include Django admin's vendored copies (plus the DAL glue code)
to keep the autocomplete widgets functional on regular (non-admin) pages.
"""

from dal_select2.widgets import (
    ModelSelect2,
    Select2WidgetMixin,
)
from django import forms
from django.conf import settings


class ThemeSelect2Mixin(Select2WidgetMixin):
    """Include jQuery, Select2 and the DAL autocomplete glue for the widgets."""

    @property
    def media(self) -> forms.Media:
        """Return the media (JS/CSS) required by DAL Select2 widgets."""
        extra = "" if settings.DEBUG else ".min"

        return forms.Media(
            js=(
                "admin/js/vendor/jquery/jquery.min.js",
                f"admin/js/vendor/select2/select2.full{extra}.js",
                f"autocomplete_light/autocomplete_light{extra}.js",
                f"autocomplete_light/select2{extra}.js",
            ),
            css={
                "screen": (
                    f"admin/css/vendor/select2/select2{extra}.css",
                    "autocomplete_light/select2.css",
                ),
            },
        )


class ThemeModelSelect2(ThemeSelect2Mixin, ModelSelect2):
    """ModelSelect2 widget using Django's vendored jQuery and Select2 assets."""

    is_select2 = True
