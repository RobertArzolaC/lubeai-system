"""Tests for the ``apps.core.templatetags.breadcrumb_tags`` tag."""

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core.templatetags.breadcrumb_tags import breadcrumb


class BreadcrumbTests(TestCase):
    """Tests for the ``breadcrumb`` template tag."""

    def test_dashboard_path_marks_dashboard_active(self) -> None:
        """On the dashboard the first crumb is marked as active."""
        request = RequestFactory().get(reverse("apps.dashboard:index"))
        crumbs = breadcrumb({"request": request})
        self.assertEqual(len(crumbs), 1)
        self.assertEqual(crumbs[0]["url"], "/dashboard/")
        self.assertTrue(crumbs[0]["is_active"])

    def test_account_list_path_builds_entity_crumb(self) -> None:
        """A list URL appends an entity crumb named after the model."""
        request = RequestFactory().get("/users/accounts/")
        crumbs = breadcrumb({"request": request})
        self.assertGreater(len(crumbs), 1)
        last = crumbs[-1]
        self.assertTrue(last["title"])
        self.assertEqual(last["url"], "/users/accounts/")
        self.assertTrue(last["is_active"])

    def test_unknown_path_keeps_dashboard_crumb(self) -> None:
        """Unresolvable path segments are skipped gracefully."""
        request = RequestFactory().get("/no/such/route/")
        crumbs = breadcrumb({"request": request})
        self.assertEqual(len(crumbs), 1)
        self.assertEqual(crumbs[0]["url"], "/dashboard/")
