"""Tests for the tenant-scoped :class:`apps.users.models.Role` model."""

from django.db import IntegrityError

from apps.organizations import factories as organization_factories
from apps.users import models as users_models
from apps.users.factories import RoleFactory
from apps.users.tests.base import UserTenantTestCase


class RoleModelTests(UserTenantTestCase):
    """Tests for the :class:`users_models.Role` model."""

    def test_unique_org_slug_constraint(self) -> None:
        """Two roles in the same organization cannot share a slug."""
        org = organization_factories.OrganizationFactory()
        RoleFactory(organization=org, slug="supervisor")
        with self.assertRaises(IntegrityError):
            RoleFactory(organization=org, slug="supervisor")

    def test_same_slug_allowed_in_different_orgs(self) -> None:
        """The constraint is per organization, not global."""
        a = organization_factories.OrganizationFactory()
        b = organization_factories.OrganizationFactory()
        RoleFactory(organization=a, slug="supervisor")
        RoleFactory(organization=b, slug="supervisor")
        self.assertEqual(users_models.Role.objects.count(), 2)

    def test_str_includes_name_and_organization(self) -> None:
        """The string representation combines the role and its organization."""
        org = organization_factories.OrganizationFactory(name="MARCO")
        role = RoleFactory(organization=org, name="Analista")
        self.assertEqual(str(role), "Analista (MARCO)")
