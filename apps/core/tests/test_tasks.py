"""Tests for the ``apps.core.tasks`` module."""

from django.test import SimpleTestCase

from apps.core.tasks import test_task


class CoreTasksTests(SimpleTestCase):
    """Tests for the shared Celery tasks."""

    def test_test_task_returns_completed(self) -> None:
        """Running the task body returns the completion marker."""
        self.assertEqual(test_task.run(), "Task completed")
