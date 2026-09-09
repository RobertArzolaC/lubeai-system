"""Tests for the ``apps.core.templatetags.common`` filters."""

from decimal import Decimal

from django.test import SimpleTestCase

from apps.core.templatetags.common import (
    divide,
    format_number,
    map_key,
    percentage,
    subtract,
)


class MapKeyTests(SimpleTestCase):
    """Tests for the ``map_key`` filter."""

    def test_returns_values_for_key(self) -> None:
        """The filter extracts the given key from a list of dicts."""
        items = [{"a": 1}, {"a": 2}, {"a": 3}]
        self.assertEqual(map_key(items, "a"), [1, 2, 3])

    def test_empty_items_returns_empty_list(self) -> None:
        """An empty list maps to an empty list."""
        self.assertEqual(map_key([], "a"), [])


class SubtractTests(SimpleTestCase):
    """Tests for the ``subtract`` filter."""

    def test_subtracts_values(self) -> None:
        """Numeric values are subtracted as floats."""
        self.assertEqual(subtract(10, 4), 6.0)

    def test_invalid_input_returns_value(self) -> None:
        """Invalid inputs are returned untouched."""
        self.assertEqual(subtract("abc", 4), "abc")


class DivideTests(SimpleTestCase):
    """Tests for the ``divide`` filter."""

    def test_divides_values(self) -> None:
        """Numeric values are divided as floats."""
        self.assertEqual(divide(10, 4), 2.5)

    def test_division_by_zero_returns_value(self) -> None:
        """Division by zero returns the original value."""
        self.assertEqual(divide(10, 0), 10)

    def test_invalid_input_returns_value(self) -> None:
        """Invalid inputs are returned untouched."""
        self.assertEqual(divide("abc", 2), "abc")


class PercentageTests(SimpleTestCase):
    """Tests for the ``percentage`` filter."""

    def test_percentage_value(self) -> None:
        """The percentage is formatted with two decimals."""
        self.assertEqual(percentage(25, 200), "12.50%")

    def test_zero_whole_returns_zero(self) -> None:
        """A zero whole avoids a division by zero error."""
        self.assertEqual(percentage(10, 0), "0%")

    def test_invalid_input(self) -> None:
        """Invalid inputs return an error marker."""
        self.assertEqual(percentage("x", 100), "Invalid input")


class FormatNumberTests(SimpleTestCase):
    """Tests for the ``format_number`` filter."""

    def test_none_returns_empty_string(self) -> None:
        """None values map to an empty string."""
        self.assertEqual(format_number(None), "")

    def test_trailing_zeros_removed(self) -> None:
        """Trailing zeros are stripped from decimals."""
        self.assertEqual(format_number("0.000"), "0")
        self.assertEqual(format_number("0.450"), "0.45")
        self.assertEqual(format_number("18.900"), "18.9")
        self.assertEqual(format_number("0.500"), "0.5")

    def test_plain_number_kept(self) -> None:
        """Numbers without decimals are preserved."""
        self.assertEqual(format_number("5"), "5")
        self.assertEqual(format_number(Decimal(7)), "7")
