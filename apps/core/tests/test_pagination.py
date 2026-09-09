"""Tests for the ``apps.core.pagination`` module."""

from django.test import SimpleTestCase

from apps.core.pagination import LargeResultsSetPagination, StandardResultsSetPagination


class PaginationClassesTests(SimpleTestCase):
    """Tests for the shared DRF pagination classes."""

    def test_large_results_pagination(self) -> None:
        """Large results use a 1000-item page size."""
        pagination = LargeResultsSetPagination()
        self.assertEqual(pagination.page_size, 1000)
        self.assertEqual(pagination.page_size_query_param, "page_size")
        self.assertEqual(pagination.max_page_size, 10000)

    def test_standard_results_pagination(self) -> None:
        """Standard results use a 100-item page size."""
        pagination = StandardResultsSetPagination()
        self.assertEqual(pagination.page_size, 100)
        self.assertEqual(pagination.page_size_query_param, "page_size")
        self.assertEqual(pagination.max_page_size, 1000)
