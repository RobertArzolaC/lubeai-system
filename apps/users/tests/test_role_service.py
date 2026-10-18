"""Tests for :class:`apps.users.services.RoleService`."""

from django.contrib.auth.models import Group, Permission

from apps.organizations import factories as organization_factories
from apps.users import models as users_models
from apps.users.factories import RoleFactory, UserFactory
from apps.users.services import RoleService
from apps.users.tests.base import UserTenantTestCase


class RoleServiceTests(UserTenantTestCase):
    """Tests for the role/group/permission synchronization."""

    def test_create_sets_permissions_and_group_name(self) -> None:
        """Creating a role stores the permissions on its backing group."""
        org = organization_factories.OrganizationFactory()
        perm = Permission.objects.get(
            codename="view_report", content_type__app_label="reports"
        )
        role = RoleService().create_role(
            organization=org, name="Analista", permissions=[perm]
        )
        self.assertEqual(role.group.name, f"org{org.id}:analista")
        self.assertEqual(list(role.group.permissions.all()), [perm])

    def test_create_assigns_actor_as_created_by(self) -> None:
        """The acting user is stored on the role when provided."""
        org = organization_factories.OrganizationFactory()
        actor = UserFactory()
        role = RoleService().create_role(organization=org, name="Analista", actor=actor)
        self.assertEqual(role.created_by, actor)

    def test_update_clears_permissions_when_empty(self) -> None:
        """Review Focus #6: an empty set persists as empty, not "unchanged"."""
        role = RoleFactory()
        permission = Permission.objects.get(codename="view_report")
        role.group.permissions.add(permission)
        RoleService().update_role(
            role, name=role.name, description=role.description, permissions=[]
        )
        self.assertEqual(role.group.permissions.count(), 0)

    def test_update_renames_group_when_slug_changes(self) -> None:
        """Renaming a role keeps the backing group name in sync."""
        org = organization_factories.OrganizationFactory()
        role = RoleFactory(organization=org, name="Analista", slug="analista")
        updated = RoleService().update_role(role, name="Supervisor")
        self.assertEqual(updated.slug, "supervisor")
        self.assertEqual(updated.group.name, f"org{org.id}:supervisor")

    def test_update_keeps_slug_on_conflict(self) -> None:
        """A colliding target slug is suffixed instead of crashing."""
        org = organization_factories.OrganizationFactory()
        RoleFactory(organization=org, slug="supervisor")
        role = RoleFactory(organization=org, name="Analista", slug="analista")
        updated = RoleService().update_role(role, name="Supervisor")
        self.assertEqual(updated.slug, "supervisor-2")

    def test_delete_removes_group(self) -> None:
        """Deleting a role removes its backing group."""
        role = RoleFactory()
        group_id = role.group_id
        RoleService().delete_role(role)
        self.assertFalse(Group.objects.filter(pk=group_id).exists())
        self.assertFalse(users_models.Role.objects.filter(pk=role.pk).exists())

    def test_unique_slug_suffixes_on_collision(self) -> None:
        """Review Focus #2: colliding slugs are suffixed, not crashed."""
        org = organization_factories.OrganizationFactory()
        RoleFactory(organization=org, name="Supervisor", slug="supervisor")
        self.assertEqual(RoleService.unique_slug(org, "Supervisor"), "supervisor-2")

    def test_build_group_name(self) -> None:
        """The group name encodes organization and slug."""
        self.assertEqual(RoleService.build_group_name(7, "analista"), "org7:analista")
