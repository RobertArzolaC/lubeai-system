"""Tests for :class:`apps.organizations.filtersets.OrganizationFilter`."""

from django.test import RequestFactory, TestCase

from apps.organizations.factories import OrganizationFactory
from apps.organizations.filtersets import OrganizationFilter
from apps.users.factories import UserFactory


class OrganizationFilterTests(TestCase):
    """Scoping and search behaviour of the organization filter."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def _request_for(self, user):
        """Build a request carrying ``user``."""
        request = self.factory.get("/")
        request.user = user
        return request

    def test_parent_filter_scoped_to_user_subtree(self) -> None:
        """The parent choices exclude organizations outside the subtree."""
        lab = OrganizationFactory()
        child = OrganizationFactory(parent=lab)
        foreign = OrganizationFactory()
        user = UserFactory(organization=lab)

        filterset = OrganizationFilter(request=self._request_for(user))

        self.assertIn(child, filterset.filters["parent"].queryset)
        self.assertNotIn(foreign, filterset.filters["parent"].queryset)

    def test_name_search_matches_slug_and_code(self) -> None:
        """Search matches name, slug and code."""
        organization = OrganizationFactory(
            name="Minera Andina", slug="minera-andina", code="ORG-00042"
        )
        filterset = OrganizationFilter({"name_search": "ORG-00042"})
        self.assertIn(organization, filterset.qs)
