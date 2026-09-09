"""Tests for the ``apps.users.filtersets`` module."""

from django.test import TestCase

from apps.users import models as users_models
from apps.users.factories import UserFactory
from apps.users.filtersets import AccountFilter


class AccountFilterTests(TestCase):
    """Tests for the :class:`AccountFilter`."""

    def setUp(self) -> None:
        self.john = UserFactory(
            email="john.smith@example.com",
            first_name="John",
            last_name="Smith",
            is_active=True,
        )
        self.maria = UserFactory(
            email="maria.doe@example.com",
            first_name="Maria",
            last_name="Doe",
            is_active=False,
        )
        self.base_queryset = users_models.Account.objects.all()

    def test_filter_by_first_name(self) -> None:
        """Filtering by first name returns matching accounts."""
        filtered = AccountFilter(
            {"name_search": "john"}, queryset=self.base_queryset
        ).qs
        self.assertQuerySetEqual(filtered, [self.john.account])

    def test_filter_by_last_name(self) -> None:
        """Filtering by last name returns matching accounts."""
        filtered = AccountFilter({"name_search": "doe"}, queryset=self.base_queryset).qs
        self.assertQuerySetEqual(filtered, [self.maria.account])

    def test_filter_by_email(self) -> None:
        """Filtering by email returns matching accounts."""
        filtered = AccountFilter(
            {"name_search": "maria.doe@example.com"},
            queryset=self.base_queryset,
        ).qs
        self.assertQuerySetEqual(filtered, [self.maria.account])

    def test_filter_is_active(self) -> None:
        """Filtering by status returns only active/inactive accounts."""
        active = AccountFilter({"is_active": "True"}, queryset=self.base_queryset).qs
        self.assertQuerySetEqual(active, [self.john.account])
        inactive = AccountFilter({"is_active": "False"}, queryset=self.base_queryset).qs
        self.assertQuerySetEqual(inactive, [self.maria.account])

    def test_no_filters_returns_all(self) -> None:
        """Without filters every account is returned."""
        filtered = AccountFilter(queryset=self.base_queryset).qs
        self.assertEqual(filtered.count(), 2)
