"""Tests for the abstract models defined in ``apps.core.models``."""

from datetime import date, timedelta

from django.conf import settings
from django.db import connection, models
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.core import models as core_models
from apps.users.factories import UserFactory


class ConcretePerson(core_models.Person):
    """Concrete subclass used to exercise the abstract ``Person`` model."""

    class Meta:
        app_label = "core"


class ConcreteStatusHistory(core_models.StatusHistory):
    """Concrete subclass that wires a parent to the status history."""

    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        app_label = "core"

    def get_parent_filters(self) -> dict:
        """Identify the history rows of the parent user."""
        return {"parent_id": self.parent_id}

    @classmethod
    def get_parent_kwargs(cls, instance) -> dict:
        """Link a history row to the parent user."""
        return {"parent": instance}


class PersonPropertiesTests(TestCase):
    """Tests for the pure helpers of the abstract :class:`Person`."""

    def setUp(self) -> None:
        self.person = ConcretePerson(
            first_name="Ana",
            paternal_last_name="Lopez",
            maternal_last_name="Rios",
            document_number="12345678",
        )

    def test_str_with_maternal_name(self) -> None:
        """String output includes all names and the document number."""
        self.assertEqual(
            str(self.person),
            "Ana Lopez Rios (12345678)",
        )

    def test_full_name_property(self) -> None:
        """``full_name`` joins first, paternal and maternal names."""
        self.assertEqual(self.person.full_name, "Ana Lopez Rios")
        self.person.maternal_last_name = ""
        self.assertEqual(self.person.full_name, "Ana Lopez")

    def test_short_name_property(self) -> None:
        """``short_name`` only uses first and paternal names."""
        self.assertEqual(self.person.short_name, "Ana Lopez")

    def test_initials_property(self) -> None:
        """``initials`` are the uppercase first letters."""
        self.assertEqual(self.person.initials, "AL")

    def test_age_with_birth_date(self) -> None:
        """``age`` is computed from the birth date."""
        today = timezone.localdate()
        self.person.birth_date = date(today.year - 20, 1, 1)
        expected = today.year - self.person.birth_date.year
        if (today.month, today.day) < (
            self.person.birth_date.month,
            self.person.birth_date.day,
        ):
            expected -= 1
        self.assertEqual(self.person.age, expected)

    def test_age_without_birth_date(self) -> None:
        """``age`` is None when no birth date is set."""
        self.person.birth_date = None
        self.assertIsNone(self.person.age)


class StatusHistoryTests(TransactionTestCase):
    """Tests for the abstract :class:`StatusHistory` model."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        with connection.schema_editor() as editor:
            editor.create_model(ConcreteStatusHistory)

    @classmethod
    def tearDownClass(cls) -> None:
        with connection.schema_editor() as editor:
            editor.delete_model(ConcreteStatusHistory)
        super().tearDownClass()

    def setUp(self) -> None:
        self.parent = UserFactory()
        self.admin = UserFactory(is_staff=True, is_superuser=True)

    def test_create_status_change_default_previous(self) -> None:
        """``create_status_change`` defaults previous status to an empty value."""
        entry = ConcreteStatusHistory.create_status_change(
            instance=self.parent, new_status="active", user=self.admin, note="ok"
        )
        self.assertEqual(entry.status, "active")
        self.assertEqual(entry.previous_status, "")
        self.assertEqual(entry.note, "ok")
        self.assertEqual(entry.created_by, self.admin)
        self.assertEqual(entry.updated_by, self.admin)
        self.assertEqual(entry.parent, self.parent)

    def test_create_status_change_with_previous(self) -> None:
        """An explicit previous status is preserved."""
        entry = ConcreteStatusHistory.create_status_change(
            instance=self.parent,
            new_status="done",
            user=self.admin,
            previous_status="active",
        )
        self.assertEqual(entry.previous_status, "active")

    def test_str_and_aliases(self) -> None:
        """String and alias helpers expose the expected values."""
        entry = ConcreteStatusHistory.objects.create(
            parent=self.parent,
            status="active",
            previous_status="pending",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.assertEqual(str(entry), "pending → active")
        self.assertEqual(entry.changed_by, self.admin)
        self.assertEqual(entry.changed_at, entry.created)

    def test_duration_in_status(self) -> None:
        """``duration_in_status`` spans until the next status change."""
        first = ConcreteStatusHistory.objects.create(
            parent=self.parent,
            status="active",
            created_by=self.admin,
            updated_by=self.admin,
        )
        past = timezone.now() - timedelta(days=2)
        ConcreteStatusHistory.objects.filter(pk=first.pk).update(created=past)
        second = ConcreteStatusHistory.objects.create(
            parent=self.parent,
            status="done",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.assertGreaterEqual(second.created, first.created)
        duration = ConcreteStatusHistory.objects.get(pk=first.pk).duration_in_status
        self.assertAlmostEqual(duration.total_seconds() / 86400, 2, delta=0.01)

    def test_duration_in_days_and_hours(self) -> None:
        """``get_duration_in_days`` and hours derive from the duration."""
        entry = ConcreteStatusHistory.objects.create(
            parent=self.parent,
            status="active",
            created_by=self.admin,
            updated_by=self.admin,
        )
        past = timezone.now() - timedelta(hours=25)
        ConcreteStatusHistory.objects.filter(pk=entry.pk).update(created=past)
        entry = ConcreteStatusHistory.objects.get(pk=entry.pk)
        self.assertEqual(entry.get_duration_in_days(), 1)
        self.assertGreaterEqual(entry.get_duration_in_hours(), 24)

    def test_meta_ordering(self) -> None:
        """Status history rows are ordered by creation descending."""
        self.assertEqual(core_models.StatusHistory._meta.ordering, ["-created"])


class BrokenStatusHistory(core_models.StatusHistory):
    """Subclass that does not implement the required parent helpers."""

    class Meta:
        app_label = "core"


class StatusHistoryContractsTests(TestCase):
    """Tests for the required subclass contracts."""

    def test_create_status_change_requires_parent_kwargs(self) -> None:
        """Subclasses must implement ``get_parent_kwargs``."""
        with self.assertRaises(NotImplementedError):
            BrokenStatusHistory.create_status_change(
                instance=UserFactory(), new_status="x", user=None
            )

    def test_get_parent_filters_raises_not_implemented(self) -> None:
        """Subclasses must implement ``get_parent_filters``."""
        entry = BrokenStatusHistory()
        with self.assertRaises(NotImplementedError):
            entry.get_parent_filters()
