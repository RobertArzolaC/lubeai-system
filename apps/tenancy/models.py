"""Shared tenancy registry: one PostgreSQL schema per platform client.

This module lives in ``SHARED_APPS``, so its models only exist in the
``public`` schema. That is what makes tenant resolution possible at all: the
registry can be queried before a tenant schema is selected.

Hard rule: a ``SHARED_APPS`` model must never have a foreign key to a
``TENANT_APPS`` model. A tenant connection searches ``<tenant>, public``, so
TENANT → SHARED works, but SHARED → TENANT would leave a dangling reference in
the public schema (the target table does not exist there). This is why
:class:`Tenant` deliberately does **not** reuse the project's
``BaseUserTracked`` mixin (``created_by``/``updated_by`` point to
``users.User``, which is a TENANT model) even though the rest of the project
uses it.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_tenants.models import DomainMixin, TenantMixin

from apps.tenancy import choices, constants


class Tenant(TenantMixin):
    """A platform client; the hard isolation boundary (one schema each).

    ``schema_name`` (inherited from :class:`~django_tenants.models.TenantMixin`)
    is the physical boundary; ``slug`` is the business identifier users and
    domains are built from, and is the single source of truth for it.
    """

    name = models.CharField(_("Name"), max_length=150)
    slug = models.SlugField(
        _("Slug"),
        max_length=63,
        unique=True,
        help_text=_("Business identifier; also used as the PostgreSQL schema name"),
    )
    kind = models.CharField(
        _("Kind"),
        max_length=20,
        choices=choices.TenantKind.choices,
        default=choices.TenantKind.FINAL,
        help_text=_("Kind of client this tenant represents"),
    )
    is_active = models.BooleanField(
        _("Is active"),
        default=True,
        help_text=_("Designates whether the tenant is served"),
    )

    # Branding: the same slots ``apps.organizations.models.Organization`` uses.
    # They are duplicated instead of imported because that app is a TENANT app.
    logo = models.ImageField(
        _("Logo"), upload_to="tenants/logos/", null=True, blank=True
    )
    primary_color = models.CharField(_("Primary color"), max_length=7, blank=True)
    chart_primary = models.CharField(_("Chart primary"), max_length=7, blank=True)
    chart_success = models.CharField(_("Chart success"), max_length=7, blank=True)
    chart_warning = models.CharField(_("Chart warning"), max_length=7, blank=True)
    chart_danger = models.CharField(_("Chart danger"), max_length=7, blank=True)
    chart_info = models.CharField(_("Chart info"), max_length=7, blank=True)
    chart_dark = models.CharField(_("Chart dark"), max_length=7, blank=True)

    capabilities = models.JSONField(
        _("Capabilities"),
        default=dict,
        blank=True,
        help_text=_("Per-tenant overrides of the kind default capabilities"),
    )

    # django-tenants creates the PostgreSQL schema together with the row.
    auto_create_schema = True

    class Meta:
        """Metadata for the tenant registry."""

        verbose_name = _("Tenant")
        verbose_name_plural = _("Tenants")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return the tenant name."""
        return self.name

    @property
    def is_ops(self) -> bool:
        """Return ``True`` when this tenant is the platform's operations tenant.

        The operations tenant is the only place where the tenant console (list,
        create, suspend and brand clients) is reachable; every other tenant
        answers 404 for those routes. It is identified by its slug so a plain
        client can never claim the console by choosing a ``kind``.
        """
        return self.slug == constants.OPS_TENANT_SLUG

    def save(self, verbosity: int = 1, *args: Any, **kwargs: Any) -> None:
        """Derive the schema name from the slug, then persist the tenant.

        Only an empty ``schema_name`` is filled in, so an existing schema is
        never renamed behind the database's back (renaming requires
        django-tenants' ``schema_rename``).

        Args:
            verbosity: Forwarded to :meth:`TenantMixin.save`; controls how much
                the schema creation logs.
            *args: Positional arguments for :meth:`TenantMixin.save`.
            **kwargs: Keyword arguments for :meth:`TenantMixin.save`.
        """
        if not self.schema_name:
            self.schema_name = self.slug

        super().save(verbosity, *args, **kwargs)


class Domain(DomainMixin):
    """A host name served by a tenant."""
