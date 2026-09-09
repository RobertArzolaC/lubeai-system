"""Tests for the ``apps.core.templatetags.pagination`` tag."""

from django.test import RequestFactory, SimpleTestCase

from apps.core.templatetags.pagination import param_replace


class ParamReplaceTests(SimpleTestCase):
    """Tests for the ``param_replace`` template tag."""

    def setUp(self) -> None:
        self.request = RequestFactory().get("/users/accounts/?page=2&x=1")

    def test_replaces_single_value(self) -> None:
        """Replacing a param keeps the remaining query parameters."""
        result = param_replace({"request": self.request}, page=1)
        self.assertIn("page=1", result)
        self.assertIn("x=1", result)
        self.assertNotIn("page=2", result)

    def test_list_value_uses_first_element(self) -> None:
        """List values are flattened to their first element."""
        result = param_replace({"request": self.request}, tag=["a", "b"])
        self.assertIn("tag=a", result)
        self.assertNotIn("tag=b", result)

    def test_empty_list_clears_param(self) -> None:
        """Empty list values clear the target parameter."""
        result = param_replace({"request": self.request}, tag=[])
        self.assertIn("tag=", result)
