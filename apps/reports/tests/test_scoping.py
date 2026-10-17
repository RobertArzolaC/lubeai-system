"""Tests for organization scoping on the report views."""

from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase

from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.reports import factories as report_factories
from apps.reports import models as report_models
from apps.reports import views
from apps.users import factories as user_factories


class ReportListViewScopingTests(TestCase):
    """The report list queryset is restricted to the user's subtree."""

    def setUp(self) -> None:
        """Create two tenants, each with a report and a permissioned user."""
        self.tenant_a = organization_factories.OrganizationFactory(
            slug="sc-a", kind=choices.OrganizationKind.LAB
        )
        self.tenant_b = organization_factories.OrganizationFactory(
            slug="sc-b", kind=choices.OrganizationKind.LAB
        )
        self.report_a = report_factories.ReportFactory(organization=self.tenant_a)
        self.report_b = report_factories.ReportFactory(organization=self.tenant_b)
        self.user_a = self._scoped_user(self.tenant_a)

    @staticmethod
    def _scoped_user(organization):
        """Return a user with ``view_report`` scoped to ``organization``."""
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        user.user_permissions.add(
            *Permission.objects.filter(codename="view_report")
        )
        return user

    def _queryset_ids(self, user):
        """Return the ids the report list view would expose to ``user``."""
        view = views.ReportListView()
        view.request = RequestFactory().get("/")
        view.request.user = user
        return set(view.get_queryset().values_list("id", flat=True))

    def test_scoped_user_only_sees_own_reports(self) -> None:
        """A tenant user does not see another tenant's reports."""
        self.assertEqual(self._queryset_ids(self.user_a), {self.report_a.id})

    def test_superuser_sees_all_reports(self) -> None:
        """A superuser sees every report."""
        superuser = user_factories.UserFactory(is_superuser=True)
        ids = self._queryset_ids(superuser)
        self.assertEqual(ids, {self.report_a.id, self.report_b.id})

    def test_unscoped_user_sees_all_reports(self) -> None:
        """A user without an organization keeps legacy unrestricted access."""
        self.assertEqual(
            self._queryset_ids(self.user_a), {self.report_a.id}
        )
        legacy = user_factories.UserFactory()
        ids = self._queryset_ids(legacy)
        self.assertIn(self.report_b.id, ids)


class ReportDetailScopingTests(TestCase):
    """Cross-tenant access to a report detail is denied."""

    def test_other_tenant_report_detail_is_not_found(self) -> None:
        """A user cannot open another tenant's report detail."""
        tenant = organization_factories.OrganizationFactory(
            slug="det-a", kind=choices.OrganizationKind.LAB
        )
        other = organization_factories.OrganizationFactory(
            slug="det-b", kind=choices.OrganizationKind.LAB
        )
        foreign_report = report_factories.ReportFactory(organization=other)

        user = user_factories.UserFactory()
        user.organization = tenant
        user.save(update_fields=["organization"])
        user.user_permissions.add(*Permission.objects.filter(codename="view_report"))
        self.client.force_login(user)

        from django.urls import reverse

        response = self.client.get(
            reverse("apps.reports:report_detail", kwargs={"pk": foreign_report.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(report_models.Report.objects.filter(pk=foreign_report.pk).exists())
