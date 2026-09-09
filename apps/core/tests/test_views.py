"""Tests for the ``apps.core.views`` error views."""

from django.test import RequestFactory, TestCase

from apps.core import views as core_views


class ErrorViewTests(TestCase):
    """Tests for the shared 404/500/403 error views."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def assert_error_response(self, view, status_code: int, template: str) -> None:
        """Render the error view and assert status code and template."""
        response = view(self.factory.get("/"))
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response.template_name, [template])

    def test_error_404_view(self) -> None:
        """The 404 view renders the 404 page with status 404."""
        self.assert_error_response(
            core_views.Error404View.as_view(), 404, "errors/404.html"
        )

    def test_error_500_view(self) -> None:
        """The 500 view renders the 500 page with status 500."""
        self.assert_error_response(
            core_views.Error500View.as_view(), 500, "errors/500.html"
        )

    def test_error_403_view(self) -> None:
        """The 403 view renders the 403 page with status 403."""
        self.assert_error_response(
            core_views.Error403View.as_view(), 403, "errors/403.html"
        )

    def test_missing_url_triggers_404_handler(self) -> None:
        """Requests to unknown paths use the 404 handler page."""
        response = self.client.get("/this-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "errors/404.html")
