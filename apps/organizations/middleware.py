"""Tenant resolution middleware.

Resolves the current tenant from the request host (subdomain) with a fallback
to ``settings.DEFAULT_TENANT_SLUG`` (useful for local development) and exposes
both ``request.tenant`` and ``request.organization`` for downstream code and
the branding context processor.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.organizations import models


class TenantMiddleware:
    """Attach the resolved tenant and organization to each request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Store the next middleware/handler callable."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Resolve the tenant/org and continue the request chain."""
        request.tenant = self._resolve_tenant(request)

        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            request.organization = getattr(user, "organization", None) or request.tenant
        else:
            request.organization = request.tenant

        return self.get_response(request)

    def _resolve_tenant(self, request: HttpRequest) -> models.Organization | None:
        """Resolve the tenant from the host slug, then the default slug."""
        host = request.get_host().split(":")[0]
        base_domain = getattr(settings, "TENANT_BASE_DOMAIN", "")

        slug: str | None = None
        if base_domain and host.endswith(f".{base_domain}"):
            slug = host[: -(len(base_domain) + 1)]

        if slug:
            tenant = models.Organization.objects.filter(
                slug=slug, is_active=True
            ).first()
            if tenant is not None:
                return tenant

        default_slug = getattr(settings, "DEFAULT_TENANT_SLUG", None)
        if default_slug:
            return models.Organization.objects.filter(
                slug=default_slug, is_active=True
            ).first()
        return None
