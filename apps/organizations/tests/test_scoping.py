"""Tests for organization-based queryset scoping.

All cases run inside a tenant schema: the platform boundary is the schema, and
the scoping rules tested here decide visibility inside one tenant's tree.
"""

from __future__ import annotations

from apps.organizations import choices, factories, scoping
from apps.organizations import models as organization_models
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.reports import models as report_models
from apps.users import factories as user_factories


class UserVisibleOrganizationIdsTests(OrganizationTenantTestCase):
    """``user_visible_organization_ids`` reflects the tenancy subtree."""

    def setUp(self) -> None:
        """Build root -> intermediary -> final plus a sibling subtree."""
        super().setUp()
        self.root = factories.OrganizationFactory(
            slug="s-root", kind=choices.OrganizationKind.LAB
        )
        self.intermediary = factories.OrganizationFactory(
            slug="s-inter",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.root,
        )
        self.final = factories.OrganizationFactory(
            slug="s-final",
            kind=choices.OrganizationKind.FINAL,
            parent=self.intermediary,
        )
        self.sibling = factories.OrganizationFactory(
            slug="s-sibling",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.root,
        )
        self.sibling_final = factories.OrganizationFactory(
            slug="s-sibling-final",
            kind=choices.OrganizationKind.FINAL,
            parent=self.sibling,
        )

    def _user_for(self, organization):
        """Return a persisted user belonging to ``organization``."""
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        return user

    def test_user_sees_only_own_subtree(self) -> None:
        """An intermediary sees itself and its final clients, not the tenant."""
        user = self._user_for(self.intermediary)
        visible = scoping.user_visible_organization_ids(user)
        self.assertEqual(visible, {self.intermediary.id, self.final.id})
        self.assertNotIn(self.root.id, visible)
        self.assertNotIn(self.sibling.id, visible)
        self.assertNotIn(self.sibling_final.id, visible)

    def test_superuser_is_unrestricted(self) -> None:
        """A superuser has no restriction."""
        user = user_factories.UserFactory(is_superuser=True)
        self.assertIsNone(scoping.user_visible_organization_ids(user))

    def test_user_without_organization_is_unrestricted(self) -> None:
        """A user without an organization keeps legacy (unrestricted) access."""
        user = user_factories.UserFactory()
        self.assertIsNone(scoping.user_visible_organization_ids(user))

    def test_platform_organization_is_unrestricted(self) -> None:
        """A user of a PLATFORM organization has no restriction."""
        platform = factories.OrganizationFactory(
            slug="s-platform", kind=choices.OrganizationKind.PLATFORM
        )
        user = self._user_for(platform)
        self.assertIsNone(scoping.user_visible_organization_ids(user))

    def test_anonymous_is_empty(self) -> None:
        """Anonymous users see nothing."""
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(scoping.user_visible_organization_ids(AnonymousUser()), set())


class ScopeQuerysetTests(OrganizationTenantTestCase):
    """``scope_queryset`` filters models with a tenancy field."""

    def setUp(self) -> None:
        """Create two sibling clients, each owning a report."""
        super().setUp()
        self.root = factories.OrganizationFactory(
            slug="s-root", kind=choices.OrganizationKind.LAB
        )
        self.client_a = factories.OrganizationFactory(
            slug="s-a", kind=choices.OrganizationKind.FINAL, parent=self.root
        )
        self.client_b = factories.OrganizationFactory(
            slug="s-b", kind=choices.OrganizationKind.FINAL, parent=self.root
        )
        self.report_a = report_models.Report.objects.create(
            lab_number="A-1", organization=self.client_a
        )
        self.report_b = report_models.Report.objects.create(
            lab_number="B-1", organization=self.client_b
        )

    def test_scopes_reports_to_visible_organizations(self) -> None:
        """Only reports of the visible organizations are returned."""
        user = user_factories.UserFactory()
        user.organization = self.client_a
        user.save(update_fields=["organization"])

        scoped = scoping.scope_queryset(report_models.Report.objects.all(), user)
        self.assertEqual(list(scoped), [self.report_a])

    def test_unscoped_user_sees_all(self) -> None:
        """A user without an organization sees everything."""
        user = user_factories.UserFactory()
        scoped = scoping.scope_queryset(report_models.Report.objects.all(), user)
        self.assertEqual(scoped.count(), 2)


class VisibleOrganizationsTests(OrganizationTenantTestCase):
    """``visible_organizations``/``can_choose_organization`` follow the subtree."""

    def setUp(self) -> None:
        """Build root -> intermediary -> final."""
        super().setUp()
        self.lab = factories.OrganizationFactory(
            slug="vo-lab", kind=choices.OrganizationKind.LAB
        )
        self.inter = factories.OrganizationFactory(
            slug="vo-inter",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.lab,
        )
        self.final = factories.OrganizationFactory(
            slug="vo-final", kind=choices.OrganizationKind.FINAL, parent=self.inter
        )

    def _user_for(self, organization):
        """Return a persisted user belonging to ``organization``."""
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        return user

    def test_intermediary_sees_subtree(self) -> None:
        """An intermediary can act on itself and its final clients."""
        user = self._user_for(self.inter)
        ids = set(scoping.visible_organizations(user).values_list("id", flat=True))
        self.assertEqual(ids, {self.inter.id, self.final.id})
        self.assertTrue(scoping.can_choose_organization(user))

    def test_leaf_cannot_choose(self) -> None:
        """A final client can only act on itself."""
        user = self._user_for(self.final)
        ids = set(scoping.visible_organizations(user).values_list("id", flat=True))
        self.assertEqual(ids, {self.final.id})
        self.assertFalse(scoping.can_choose_organization(user))

    def test_subtree_scoping_still_isolates_children(self) -> None:
        """A final client cannot see a sibling subtree."""
        sibling = factories.OrganizationFactory(
            slug="vo-sibling",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.lab,
        )
        sibling_final = factories.OrganizationFactory(
            slug="vo-sibling-final",
            kind=choices.OrganizationKind.FINAL,
            parent=sibling,
        )

        user = self._user_for(self.final)
        ids = set(scoping.visible_organizations(user).values_list("id", flat=True))

        self.assertEqual(ids, {self.final.id})
        self.assertNotIn(sibling.id, ids)
        self.assertNotIn(sibling_final.id, ids)

    def test_unrestricted_user_sees_all(self) -> None:
        """An unassigned user is unrestricted and can choose."""
        user = user_factories.UserFactory()
        self.assertIsNone(scoping.user_visible_organization_ids(user))
        self.assertTrue(scoping.can_choose_organization(user))

    def test_anonymous_cannot_choose(self) -> None:
        """Anonymous users cannot choose an organization."""
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(scoping.can_choose_organization(AnonymousUser()))

    def test_is_organization_visible(self) -> None:
        """Visibility accepts descendants and rejects ancestors and ``None``."""
        user = self._user_for(self.inter)
        self.assertTrue(scoping.is_organization_visible(user, self.final))
        self.assertFalse(scoping.is_organization_visible(user, self.lab))
        self.assertFalse(scoping.is_organization_visible(user, None))


class VisibleOrganizationsStrictChildrenTests(OrganizationTenantTestCase):
    """``include_self=False`` excludes the user's own organization."""

    def setUp(self) -> None:
        """Build a lab with one final client."""
        super().setUp()
        self.lab = factories.OrganizationFactory(
            slug="vc-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = factories.OrganizationFactory(
            slug="vc-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )

    def _user_for(self, organization):
        """Return a persisted user belonging to ``organization``."""
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        return user

    def test_exclude_self_returns_only_descendants(self) -> None:
        """A parent user only sees its descendants in the strict listing."""
        user = self._user_for(self.lab)
        ids = set(
            scoping.visible_organizations(user, include_self=False).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(ids, {self.final.id})

    def test_include_self_keeps_own_organization(self) -> None:
        """The default keeps the user's own organization in the listing."""
        user = self._user_for(self.lab)
        ids = set(
            scoping.visible_organizations(user, include_self=True).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(ids, {self.lab.id, self.final.id})

    def test_exclude_self_leaf_returns_nothing(self) -> None:
        """A leaf user has no descendants."""
        user = self._user_for(self.final)
        self.assertFalse(
            scoping.visible_organizations(user, include_self=False).exists()
        )

    def test_exclude_self_unrestricted_returns_all(self) -> None:
        """An unrestricted user still sees every organization."""
        user = user_factories.UserFactory()
        ids = set(
            scoping.visible_organizations(user, include_self=False).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(
            ids,
            set(organization_models.Organization.objects.values_list("id", flat=True)),
        )
        self.assertIn(self.lab.id, ids)
        self.assertIn(self.final.id, ids)
