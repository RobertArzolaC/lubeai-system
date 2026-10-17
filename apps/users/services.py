"""Services for the users app.

:class:`RoleService` keeps a tenant-scoped :class:`~apps.users.models.Role` and
its backing Django :class:`~django.contrib.auth.models.Group` in sync (name and
permissions). Business logic lives here so views and forms stay thin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import Group, Permission
from django.utils.text import slugify

from apps.users import models

if TYPE_CHECKING:
    from collections.abc import Iterable

    from apps.organizations import models as organization_models
    from apps.users.models import User


class RoleService:
    """Create, update and delete roles together with their Django group."""

    @staticmethod
    def build_group_name(organization_id: int, slug: str) -> str:
        """Return the globally unique group name for a role.

        Args:
            organization_id: Id of the owning organization.
            slug: The role slug (unique within the organization).

        Returns:
            The group name, e.g. ``org7:analista``.
        """
        return f"org{organization_id}:{slug}"

    @staticmethod
    def unique_slug(
        organization: organization_models.Organization,
        name: str,
        *,
        exclude_pk: int | None = None,
    ) -> str:
        """Return a role slug unique within ``organization``.

        Args:
            organization: The owning organization.
            name: The human-readable role name to slugify.
            exclude_pk: A role id to ignore (used when renaming).

        Returns:
            A slug, suffixed with ``-2``, ``-3``, ... on collision.
        """
        base = slugify(name) or "role"
        queryset = models.Role.objects.filter(organization=organization, slug=base)
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        if not queryset.exists():
            return base

        suffix = 2
        while True:
            candidate = f"{base}-{suffix}"
            exists = models.Role.objects.filter(
                organization=organization, slug=candidate
            ).exists()
            if not exists:
                return candidate
            suffix += 1

    def create_role(
        self,
        *,
        organization: organization_models.Organization,
        name: str,
        description: str = "",
        permissions: Iterable[Permission] = (),
        actor: User | None = None,
    ) -> models.Role:
        """Create a role and its backing group with the given permissions.

        Args:
            organization: The organization the role belongs to.
            name: The role display name.
            description: Optional description.
            permissions: Permissions to grant to the role.
            actor: The user creating the role (stored as ``created_by``).

        Returns:
            The newly created :class:`~apps.users.models.Role`.
        """
        slug = self.unique_slug(organization, name)
        group = Group.objects.create(
            name=self.build_group_name(organization.pk, slug)
        )
        group.permissions.set(permissions)
        return models.Role.objects.create(
            organization=organization,
            name=name,
            slug=slug,
            description=description,
            group=group,
            created_by=actor,
            updated_by=actor,
        )

    def update_role(
        self,
        role: models.Role,
        *,
        name: str,
        description: str = "",
        is_active: bool = True,
        permissions: Iterable[Permission] = (),
        actor: User | None = None,
    ) -> models.Role:
        """Update a role, renaming its group if the slug changes.

        The permission set is always replaced, so an empty iterable clears the
        role's permissions (it does not mean "leave unchanged").

        Args:
            role: The role to update.
            name: The new display name.
            description: The new description.
            is_active: Whether the role is active.
            permissions: The full permission set for the role.
            actor: The user performing the update (stored as ``updated_by``).

        Returns:
            The updated role.
        """
        slug = self.unique_slug(role.organization, name, exclude_pk=role.pk)

        role.name = name
        role.description = description
        role.is_active = is_active
        role.updated_by = actor

        if role.group_id is not None:
            role.group.permissions.set(permissions)
            if slug != role.slug:
                role.group.name = self.build_group_name(role.organization_id, slug)
                role.group.save(update_fields=["name"])

        role.slug = slug
        role.save()
        return role

    def delete_role(self, role: models.Role) -> None:
        """Delete a role by deleting its backing group (the role cascades).

        Args:
            role: The role to delete.
        """
        group = role.group
        if group is not None:
            group.delete()
        else:
            role.delete()
