"""Models for the organizations app.

:class:`Organization` models the tenancy tree. A node without a parent is a
tenant (the hard isolation boundary); children are the tenant's clients
(intermediaries and final clients). Branding is inherited from ancestors and
capabilities default from the tenant ``kind`` with per-node overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel

from apps.core import models as core_models
from apps.organizations import choices, constants

if TYPE_CHECKING:
    from django.db.models import QuerySet


class Organization(
    TimeStampedModel,
    core_models.BaseUserTracked,
    core_models.BaseContact,
    core_models.IsActive,
):
    """A node in the tenancy tree (tenant, intermediary or final client)."""

    name = models.CharField(_("Name"), max_length=200)
    slug = models.SlugField(
        _("Slug"),
        max_length=120,
        unique=True,
        help_text=_("Used to resolve the tenant from the request host"),
    )
    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Optional business code"),
    )
    description = models.TextField(_("Description"), blank=True)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Parent organization"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text=_("Empty for a root tenant"),
    )
    kind = models.CharField(
        _("Kind"),
        max_length=20,
        choices=choices.OrganizationKind.choices,
        default=choices.OrganizationKind.FINAL,
        help_text=_("Determines default capabilities"),
    )

    # Branding (inherited from ancestors when empty).
    logo = models.ImageField(
        _("Logo"), upload_to="organizations/logos/", null=True, blank=True
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
        help_text=_("Per-organization overrides of the kind default capabilities"),
    )

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ("name",)
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["slug"]),
            models.Index(fields=["kind"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        """Return the organization name."""
        return self.name

    @property
    def is_tenant(self) -> bool:
        """Return ``True`` when the organization is a root tenant."""
        return self.parent_id is None

    @property
    def tenant(self) -> Organization:
        """Return the root tenant the organization belongs to."""
        node: Organization = self
        while node.parent_id is not None:
            node = node.parent
        return node

    def ancestors(self, include_self: bool = False) -> list[Organization]:
        """Return the ancestor chain ordered from the node up to the root."""
        chain: list[Organization] = [self] if include_self else []
        node = self.parent
        while node is not None:
            chain.append(node)
            node = node.parent
        return chain

    def descendants(self, include_self: bool = True) -> QuerySet[Organization]:
        """Return the whole subtree rooted at this organization."""
        ids: list[int] = [self.pk]
        frontier: list[int] = [self.pk]
        while frontier:
            children = list(
                Organization.objects.filter(parent_id__in=frontier).values_list(
                    "pk", flat=True
                )
            )
            frontier = [child for child in children if child not in ids]
            ids.extend(frontier)

        queryset = Organization.objects.filter(pk__in=ids)
        if not include_self:
            queryset = queryset.exclude(pk=self.pk)
        return queryset

    def get_branding(self) -> dict:
        """Return the resolved branding, inheriting from ancestors.

        Child values win over ancestors; missing slots fall back to
        :data:`apps.organizations.constants.DEFAULT_BRANDING`.
        """
        branding: dict = dict(constants.DEFAULT_BRANDING)
        chain = list(reversed(self.ancestors(include_self=True)))

        for node in chain:
            for slot in constants.BRANDING_SLOTS:
                value = getattr(node, slot, "")
                if value:
                    branding[slot] = value

        logo = None
        for node in chain:
            if node.logo:
                logo = node.logo
        branding["logo"] = logo
        return branding

    def resolved_capabilities(self) -> dict:
        """Return capabilities merged from the tenant down to this node."""
        chain = list(reversed(self.ancestors(include_self=True)))
        capabilities: dict = dict(constants.DEFAULT_CAPABILITIES.get(chain[0].kind, {}))
        for node in chain:
            capabilities.update(node.capabilities or {})
        return capabilities

    def has_capability(self, key: str) -> bool:
        """Return ``True`` when the resolved capabilities enable ``key``."""
        return bool(self.resolved_capabilities().get(key, False))
