"""Organization resolution middleware.

``TenantMainMiddleware`` resolves the platform client from the request host and
leaves it on ``request.tenant``. Inside that schema the client tree still
matters — branding is inherited parent to child and object scoping is subtree
based — so this middleware publishes the organization **in effect** for the
request as ``request.organization``:

* an authenticated user with an organization gets its own node (and, through
  :meth:`apps.organizations.models.Organization.get_branding`, the branding
  inherited from its ancestors);
* everybody else — anonymous visitors and users without an organization — gets
  ``request.tenant``, which stands in for the root organization of the tenant's
  own tree;
* a request outside any tenant (the ``public`` schema, error pages, background
  jobs) gets ``None``.

It must run after
:class:`~django_tenants.middleware.main.TenantMainMiddleware` (which sets
``request.tenant``) and after
:class:`~django.contrib.auth.middleware.AuthenticationMiddleware` (which sets
``request.user``).
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.organizations import models as organization_models
from apps.tenancy import models as tenancy_models

OrganizationInEffect = organization_models.Organization | tenancy_models.Tenant | None


class OrganizationMiddleware:
    """Attach the organization in effect to every request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Store the next middleware or view callable.

        Args:
            get_response: The next callable in the middleware chain.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Resolve ``request.organization`` and continue the request chain.

        Args:
            request: The current HTTP request.

        Returns:
            The response produced downstream.
        """
        request.organization = self.resolve_organization(request)
        return self.get_response(request)

    @staticmethod
    def resolve_organization(request: HttpRequest) -> OrganizationInEffect:
        """Return the organization in effect for ``request``.

        Args:
            request: The current HTTP request, once the tenancy and
                authentication middleware have run.

        Returns:
            The authenticated user's own organization when it has one,
            otherwise ``request.tenant`` (the root organization of the tenant's
            tree), or ``None`` when the request is not served from a tenant
            schema.
        """
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            organization = getattr(user, "organization", None)
            if organization is not None:
                return organization
        return getattr(request, "tenant", None)
