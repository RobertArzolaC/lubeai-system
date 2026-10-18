"""Tests for the ``apps.users.models`` module."""

from allauth.account.models import EmailAddress
from django.db import IntegrityError

from apps.users.factories import UserFactory
from apps.users.tests.base import UserTenantTestCase


class UserModelTests(UserTenantTestCase):
    """Tests for the :class:`users_models.User` model."""

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory(
            email="jane.doe@example.com",
            first_name="Jane",
            last_name="Doe",
        )

    def test_user_str_returns_email(self) -> None:
        """The string representation of a user is its email."""
        self.assertEqual(str(self.user), "jane.doe@example.com")

    def test_full_name_combines_first_and_last(self) -> None:
        """``full_name`` joins first and last names."""
        self.assertEqual(self.user.full_name, "Jane Doe")

    def test_is_email_verified_on_user_true_when_verified(self) -> None:
        """``User.is_email_verified`` is True for a verified email."""
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )
        self.assertTrue(self.user.is_email_verified)

    def test_is_email_verified_on_user_false_when_unverified(self) -> None:
        """``User.is_email_verified`` is False when no email is verified."""
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=False
        )
        self.assertFalse(self.user.is_email_verified)

    def test_user_cannot_have_duplicate_email(self) -> None:
        """Creating two users with the same email raises IntegrityError."""
        with self.assertRaises(IntegrityError):
            UserFactory(email="jane.doe@example.com")

    def test_tenant_returns_root_organization(self) -> None:
        """``tenant`` resolves the root of the user's organization tree."""
        from apps.organizations.factories import OrganizationFactory

        root = OrganizationFactory()
        self.user.organization = root
        self.user.save(update_fields=["organization"])
        self.assertEqual(self.user.tenant, root)
