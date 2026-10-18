"""Tests for the organization middleware.

``request.organization`` is the organization **in effect** for a request: the
organization of the authenticated user when it has one, otherwise the tenant —
which stands in for the root organization of its own client tree — and ``None``
when the request is not served from a tenant schema at all.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.organizations import choices, middleware, models
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.users.factories import UserFactory

TENANT_MIDDLEWARE = "django_tenants.middleware.main.TenantMainMiddleware"
AUTH_MIDDLEWARE = "django.contrib.auth.middleware.AuthenticationMiddleware"
ORGANIZATION_MIDDLEWARE = "apps.organizations.middleware.OrganizationMiddleware"


class OrganizationMiddlewareSettingsTests(TestCase):
    """The middleware must see both the tenant and the authenticated user."""

    def test_middleware_is_installed_after_tenant_and_authentication(self) -> None:
        """Resolving the organization needs ``request.tenant`` and ``request.user``."""
        self.assertIn(ORGANIZATION_MIDDLEWARE, settings.MIDDLEWARE)

        index = settings.MIDDLEWARE.index(ORGANIZATION_MIDDLEWARE)
        self.assertGreater(index, settings.MIDDLEWARE.index(TENANT_MIDDLEWARE))
        self.assertGreater(index, settings.MIDDLEWARE.index(AUTH_MIDDLEWARE))


class OrganizationMiddlewareTests(OrganizationTenantTestCase):
    """Tests for the organization attached to each request."""

    def setUp(self) -> None:
        """Build the tenant's client tree."""
        super().setUp()
        self.root = models.Organization.objects.create(
            name="ACME Peru",
            slug="acme-peru",
            kind=choices.OrganizationKind.LAB,
        )
        self.branch = models.Organization.objects.create(
            name="Planta Norte",
            slug="planta-norte",
            kind=choices.OrganizationKind.FINAL,
            parent=self.root,
        )
        self.url = reverse("apps.users:profile")

    def test_authenticated_user_gets_its_own_organization(self) -> None:
        """A user belonging to a node gets that node, not the tenant."""
        self.client.force_login(UserFactory(organization=self.branch))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.organization, self.branch)

    def test_user_without_organization_falls_back_to_the_tenant(self) -> None:
        """A user with no organization gets the tenant's own root."""
        self.client.force_login(UserFactory(is_superuser=True, organization=None))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.organization, self.tenant)

    def test_anonymous_request_falls_back_to_the_tenant(self) -> None:
        """The login page is branded by the tenant itself."""
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.organization, self.tenant)

    def test_request_outside_a_tenant_has_no_organization(self) -> None:
        """A request with no tenant in scope gets ``None``, not an error."""
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        seen: dict[str, object] = {}

        def get_response(inner_request: HttpRequest) -> HttpResponse:
            """Record the request as the view would see it."""
            seen["organization"] = inner_request.organization
            return HttpResponse()

        response = middleware.OrganizationMiddleware(get_response)(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(request.organization)
        self.assertIsNone(seen["organization"])
