"""Tests for organization-based queryset scoping."""

from django.test import TestCase

from apps.organizations import choices, factories, scoping
from apps.reports import models as report_models
from apps.users import factories as user_factories


class UserVisibleOrganizationIdsTests(TestCase):
    """``user_visible_organization_ids`` reflects the tenancy subtree."""

    def setUp(self) -> None:
        """Build MARCO -> intermediary -> final plus an unrelated tenant."""
        self.marco = factories.OrganizationFactory(
            slug="s-marco", kind=choices.OrganizationKind.LAB
        )
        self.intermediary = factories.OrganizationFactory(
            slug="s-inter",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.marco,
        )
        self.final = factories.OrganizationFactory(
            slug="s-final", kind=choices.OrganizationKind.FINAL, parent=self.intermediary
        )
        self.other = factories.OrganizationFactory(
            slug="s-other", kind=choices.OrganizationKind.LAB
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
        self.assertNotIn(self.marco.id, visible)
        self.assertNotIn(self.other.id, visible)

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


class ScopeQuerysetTests(TestCase):
    """``scope_queryset`` filters models with a tenancy field."""

    def setUp(self) -> None:
        """Create two tenants each owning a report."""
        self.tenant_a = factories.OrganizationFactory(
            slug="s-a", kind=choices.OrganizationKind.LAB
        )
        self.tenant_b = factories.OrganizationFactory(
            slug="s-b", kind=choices.OrganizationKind.LAB
        )
        self.report_a = report_models.Report.objects.create(
            lab_number="A-1", organization=self.tenant_a
        )
        self.report_b = report_models.Report.objects.create(
            lab_number="B-1", organization=self.tenant_b
        )

    def test_scopes_reports_to_visible_organizations(self) -> None:
        """Only reports of the visible organizations are returned."""
        user = user_factories.UserFactory()
        user.organization = self.tenant_a
        user.save(update_fields=["organization"])

        scoped = scoping.scope_queryset(report_models.Report.objects.all(), user)
        self.assertEqual(list(scoped), [self.report_a])

    def test_unscoped_user_sees_all(self) -> None:
        """A user without an organization sees everything."""
        user = user_factories.UserFactory()
        scoped = scoping.scope_queryset(report_models.Report.objects.all(), user)
        self.assertEqual(scoped.count(), 2)


class VisibleOrganizationsTests(TestCase):
    """``visible_organizations``/``can_choose_organization`` follow the subtree."""

    def setUp(self) -> None:
        """Build lab -> intermediary -> final."""
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
