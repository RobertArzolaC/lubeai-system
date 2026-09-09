"""Tests for the ``apps.core.choices`` module."""

from django.test import SimpleTestCase

from apps.core import choices


class StatusChoicesTests(SimpleTestCase):
    """Tests for the :class:`StatusChoices` enumeration."""

    def test_values_and_labels(self) -> None:
        """Every status has the expected value and a non-empty label."""
        self.assertEqual(
            [member.value for member in choices.StatusChoices],
            list(range(7)),
        )
        for member in choices.StatusChoices:
            self.assertTrue(member.label)


class MonthChoicesTests(SimpleTestCase):
    """Tests for the :class:`MonthChoices` enumeration."""

    def test_month_boundaries(self) -> None:
        """Months span from January (1) to December (12)."""
        self.assertEqual(choices.MonthChoices.JANUARY.value, 1)
        self.assertEqual(choices.MonthChoices.DECEMBER.value, 12)


class DocumentTypeTests(SimpleTestCase):
    """Tests for the :class:`DocumentType` enumeration."""

    def test_document_type_values(self) -> None:
        """Document types use the expected stored values."""
        self.assertEqual(
            [member.value for member in choices.DocumentType],
            ["DNI", "RUC", "PASSPORT", "FOREIGN_ID"],
        )


class GenderTests(SimpleTestCase):
    """Tests for the :class:`Gender` enumeration."""

    def test_gender_values(self) -> None:
        """Genders use the expected stored values."""
        self.assertEqual([member.value for member in choices.Gender], ["M", "F", "O"])
