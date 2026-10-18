"""Tests for :class:`apps.users.filtersets.UserFilter`."""

from django.test import RequestFactory

from apps.organizations.factories import OrganizationFactory
from apps.users.factories import RoleFactory, UserFactory
from apps.users.filtersets import UserFilter
from apps.users.tests.base import UserTenantTestCase


class UserFilterTests(UserTenantTestCase):
    """Scoping and search behaviour of the user filter."""

    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()
        self.lab = OrganizationFactory()
        self.child = OrganizationFactory(parent=self.lab)
        self.actor = UserFactory(organization=self.lab)

    def _request(self):
        request = self.factory.get("/")
        request.user = self.actor
        return request

    def test_role_filter_scoped_to_subtree(self) -> None:
        """The role choices exclude roles outside the actor's subtree."""
        own_role = RoleFactory(organization=self.lab)
        foreign_role = RoleFactory(organization=OrganizationFactory())

        filterset = UserFilter(request=self._request())

        self.assertIn(own_role, filterset.filters["role"].queryset)
        self.assertNotIn(foreign_role, filterset.filters["role"].queryset)

    def test_name_search_matches_email(self) -> None:
        """Search matches the user's email."""
        member = UserFactory(organization=self.lab, email="target@example.com")
        filterset = UserFilter({"name_search": "target@example.com"})
        self.assertIn(member, filterset.qs)
