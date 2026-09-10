"""Tests for the ``apps.alerts.filtersets`` module."""

from datetime import datetime

from django import forms
from django.test import TestCase
from django.utils import timezone

from apps.alerts import factories, filtersets, models


def aware(year: int, month: int, day: int) -> datetime:
    """Return a timezone-aware datetime for the given date."""
    return datetime(year, month, day, tzinfo=timezone.get_current_timezone())


class AlertFilterTests(TestCase):
    """Tests for :class:`AlertFilter`."""

    def setUp(self) -> None:
        machine = factories.equipment_factories.MachineFactory(name="Main Engine")
        component = factories.equipment_factories.ComponentFactory(machine=machine)
        self.alert = factories.AlertFactory(
            machine=machine,
            component=component,
            parameter="iron_fe",
            category="wear_metals",
            severity="CRITICAL",
            status="OPEN",
            dedup_key="alert-one",
            detected_at=aware(2024, 6, 15),
        )
        self.other = factories.AlertFactory(
            parameter="copper_cu",
            category="contamination",
            severity="WARNING",
            status="RESOLVED",
            dedup_key="alert-two",
            detected_at=aware(2023, 1, 10),
        )

    def filter_qs(self, **params):
        """Return the queryset produced by the filter with ``params``."""
        return filtersets.AlertFilter(params, queryset=models.Alert.objects.all()).qs

    def test_filter_by_severity(self) -> None:
        """``severity`` filters by alert severity."""
        queryset = self.filter_qs(severity="CRITICAL")
        self.assertIn(self.alert, queryset)
        self.assertNotIn(self.other, queryset)

    def test_filter_by_status(self) -> None:
        """``status`` filters by lifecycle status."""
        queryset = self.filter_qs(status="RESOLVED")
        self.assertIn(self.other, queryset)
        self.assertNotIn(self.alert, queryset)

    def test_filter_by_parameter(self) -> None:
        """``parameter`` filters by analysis parameter."""
        queryset = self.filter_qs(parameter="iron_fe")
        self.assertIn(self.alert, queryset)
        self.assertNotIn(self.other, queryset)

    def test_filter_by_machine(self) -> None:
        """``machine`` filters by the related machine."""
        queryset = self.filter_qs(machine=self.alert.machine_id)
        self.assertIn(self.alert, queryset)
        self.assertNotIn(self.other, queryset)

    def test_filter_by_search_matches_dedup_key(self) -> None:
        """``search`` matches the deduplication key."""
        queryset = self.filter_qs(search="alert-two")
        self.assertIn(self.other, queryset)
        self.assertNotIn(self.alert, queryset)

    def test_filter_by_search_matches_machine_name(self) -> None:
        """``search`` matches the related machine name."""
        queryset = self.filter_qs(search="Main Engine")
        self.assertIn(self.alert, queryset)
        self.assertNotIn(self.other, queryset)

    def test_filter_by_detected_range(self) -> None:
        """``detected_after`` and ``detected_before`` bound the detection date."""
        queryset = self.filter_qs(
            detected_after="2024-01-01", detected_before="2024-12-31"
        )
        self.assertIn(self.alert, queryset)
        self.assertNotIn(self.other, queryset)

    def test_date_filters_use_date_inputs(self) -> None:
        """The date filters render as native date inputs."""
        filterset = filtersets.AlertFilter()
        for name in ("detected_after", "detected_before"):
            with self.subTest(field=name):
                widget = filterset.filters[name].field.widget
                self.assertIsInstance(widget, forms.DateInput)
                self.assertEqual(widget.input_type, "date")
