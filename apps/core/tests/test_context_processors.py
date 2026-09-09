"""Tests for the ``apps.core.context_processors`` module."""

from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase

from apps.core.context_processors import site_processor


class SiteProcessorTests(TestCase):
    """Tests for the :func:`site_processor` context processor."""

    def setUp(self) -> None:
        self.request = RequestFactory().get("/")

    def test_returns_current_site(self) -> None:
        """The processor exposes the current Site under the ``site`` key."""
        context = site_processor(self.request)
        self.assertIn("site", context)
        self.assertIsInstance(context["site"], Site)
        self.assertEqual(context["site"].pk, 1)
