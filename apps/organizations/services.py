"""Services for the organizations app."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.organizations import constants, models


class ColorPaletteService:
    """Resolve the chart color palette for an organization.

    The palette keys match the branding slots (``chart_primary``,
    ``chart_success``, ``chart_warning``, ``chart_danger``, ``chart_info``,
    ``chart_dark``) so callers can resolve a color by slot name.
    """

    @staticmethod
    def get_palette(organization: object | None = None) -> dict:
        """Return the palette for ``organization`` (defaults when ``None``).

        Args:
            organization: An ``Organization`` instance or ``None``.

        Returns:
            Mapping of branding slot names to hex colors.
        """
        if organization is None:
            return dict(constants.DEFAULT_BRANDING)
        return organization.get_branding()


class OrganizationService:
    """Business rules for managing organizations in the tenancy tree."""

    @staticmethod
    def ensure_unique_slug(name: str, *, exclude_pk: int | None = None) -> str:
        """Return a slug derived from ``name`` that is globally unique.

        Args:
            name: The human-readable organization name.
            exclude_pk: An organization id to ignore (used when renaming).

        Returns:
            A slug, suffixed with ``-2``, ``-3``, ... on collision.
        """
        base = slugify(name) or "organization"
        queryset = models.Organization.objects.filter(slug=base)
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        if not queryset.exists():
            return base

        suffix = 2
        while True:
            candidate = f"{base}-{suffix}"
            if not models.Organization.objects.filter(slug=candidate).exists():
                return candidate
            suffix += 1

    @staticmethod
    def assert_valid_parent(
        organization: models.Organization,
        parent: models.Organization | None,
    ) -> None:
        """Reject a parent that would create a cycle in the tree.

        Args:
            organization: The organization being assigned a parent.
            parent: The candidate parent (``None`` for a root).

        Raises:
            ValidationError: If ``parent`` is the organization itself or one of
                its descendants.
        """
        if parent is None or organization.pk is None:
            return
        descendant_ids = set(
            organization.descendants(include_self=True).values_list("pk", flat=True)
        )
        if parent.pk in descendant_ids:
            raise ValidationError(
                _("An organization cannot be its own parent or descendant."),
                code="invalid",
            )

    @staticmethod
    def deactivate(organization: models.Organization) -> None:
        """Deactivate an organization and its whole subtree.

        Args:
            organization: The subtree root to deactivate.
        """
        organization.descendants(include_self=True).update(is_active=False)

    @staticmethod
    def delete_organization(organization: models.Organization) -> None:
        """Delete a leaf organization that has no children or users.

        Args:
            organization: The organization to delete.

        Raises:
            ValidationError: If the organization still has child organizations
                or users (deleting it would cascade-destroy them).
        """
        if organization.children.exists() or organization.users.exists():
            raise ValidationError(
                _("This organization still has child organizations or users."),
                code="in-use",
            )
        organization.delete()
