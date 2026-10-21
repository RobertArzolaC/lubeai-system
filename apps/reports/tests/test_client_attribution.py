"""Tests for client attribution on the report and threshold lists."""

from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.test import RequestFactory
from django.urls import reverse

from apps.core.tests.base import TenantSchemaTestCase
from apps.equipment import factories as equipment_factories
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.organizations import models as organization_models
from apps.reports import factories, filtersets, models
from apps.reports import views as report_views
from apps.users import factories as user_factories
from apps.users import models as user_models


def user_for(organization: organization_models.Organization) -> user_models.User:
    """Return a persisted user belonging to ``organization``."""
    user = user_factories.UserFactory()
    user.organization = organization
    user.save(update_fields=["organization"])
    return user


def grant_permissions(user: user_models.User, *codenames: str) -> None:
    """Grant the given reports permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="reports", codename__in=codenames
    )
    user.user_permissions.add(*permissions)


def list_context(view_class, user: user_models.User) -> dict:
    """Return the context of the list ``view_class`` for ``user``."""
    request = RequestFactory().get("/")
    request.user = user
    view = view_class()
    view.request = request
    view.kwargs = {}
    view.object_list = view.get_queryset()
    return view.get_context_data()


class ReportClientAttributionTests(TenantSchemaTestCase):
    """Client attribution for the report list view and filter."""

    def setUp(self) -> None:
        """Build a lab with one final client."""
        super().setUp()
        self.lab = organization_factories.OrganizationFactory(
            slug="ra-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="ra-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.lab_user = user_for(self.lab)
        self.final_user = user_for(self.final)

    def test_show_organization_true_for_parent(self) -> None:
        """A parent user sees the client column and filter."""
        context = list_context(report_views.ReportListView, self.lab_user)
        self.assertTrue(context["show_organization"])

    def test_show_organization_false_for_leaf(self) -> None:
        """A leaf user does not see the client column and filter."""
        context = list_context(report_views.ReportListView, self.final_user)
        self.assertFalse(context["show_organization"])

    def test_organization_filter_lists_strict_children(self) -> None:
        """The filter only offers the user's descendants."""
        filterset = filtersets.ReportFilter(
            queryset=models.Report.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(
            filterset.filters["organization"].queryset.values_list("id", flat=True)
        )
        self.assertEqual(ids, {self.final.id})

    def test_filter_by_organization(self) -> None:
        """Filtering by a child organization narrows the reports."""
        report_lab = factories.ReportFactory(organization=self.lab)
        report_final = factories.ReportFactory(organization=self.final)
        filterset = filtersets.ReportFilter(
            {"organization": self.final.pk},
            queryset=models.Report.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(filterset.qs.values_list("id", flat=True))
        self.assertEqual(ids, {report_final.id})
        self.assertNotIn(report_lab.id, ids)


class ReportComponentScopingTests(TenantSchemaTestCase):
    """Component filter choices stay inside the user's organization tree."""

    def setUp(self) -> None:
        """Build one visible organization and one unrelated tenant."""
        super().setUp()
        self.org = organization_factories.OrganizationFactory(
            slug="rcs-own", kind=choices.OrganizationKind.FINAL
        )
        self.other = organization_factories.OrganizationFactory(
            slug="rcs-other", kind=choices.OrganizationKind.FINAL
        )
        self.user = user_for(self.org)
        self.machine = equipment_factories.MachineFactory(organization=self.org)
        self.component = equipment_factories.ComponentFactory(machine=self.machine)
        self.foreign_machine = equipment_factories.MachineFactory(
            organization=self.other
        )
        self.foreign_component = equipment_factories.ComponentFactory(
            machine=self.foreign_machine
        )

    def test_component_choices_exclude_other_organizations(self) -> None:
        """A machine from another tenant exposes none of its components."""
        filterset = filtersets.ReportFilter(
            {"machine": self.foreign_machine.pk},
            queryset=models.Report.objects.all(),
            request=SimpleNamespace(user=self.user),
        )
        self.assertFalse(filterset.filters["component"].queryset.exists())

    def test_export_component_choices_exclude_other_organizations(self) -> None:
        """The export page does not render components from other tenants."""
        grant_permissions(self.user, "view_report")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.reports:report_export"))
        self.assertNotContains(response, str(self.foreign_component))


class ReportClientColumnTemplateTests(TenantSchemaTestCase):
    """The report list renders the Client column and filter for parent users."""

    def setUp(self) -> None:
        """Build a lab with one final client, each owning a report."""
        super().setUp()
        self.lab = organization_factories.OrganizationFactory(
            slug="rct-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="rct-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.lab_user = user_for(self.lab)
        grant_permissions(self.lab_user, "view_report")
        self.final_user = user_for(self.final)
        grant_permissions(self.final_user, "view_report")
        factories.ReportFactory(organization=self.lab)
        factories.ReportFactory(organization=self.final)

    def test_parent_sees_client_filter_and_column(self) -> None:
        """A parent user gets the Client select and header."""
        self.client.force_login(self.lab_user)
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertContains(response, 'id="id_organization"')
        self.assertContains(response, ">Cliente<")
        self.assertContains(response, self.final.name)

    def test_leaf_sees_no_client_filter(self) -> None:
        """A leaf user gets no Client select."""
        self.client.force_login(self.final_user)
        response = self.client.get(reverse("apps.reports:report_list"))
        self.assertNotContains(response, 'id="id_organization"')


class ThresholdClientAttributionTests(TenantSchemaTestCase):
    """Client attribution and scoping for the threshold list."""

    def setUp(self) -> None:
        """Build a lab, a child client and an unrelated tenant."""
        super().setUp()
        self.lab = organization_factories.OrganizationFactory(
            slug="ta-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="ta-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.other = organization_factories.OrganizationFactory(
            slug="ta-other", kind=choices.OrganizationKind.LAB
        )
        self.lab_threshold = factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.lab
            ),
            category="wear_metals",
            parameter="iron_fe",
        )
        self.final_threshold = factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.final
            ),
            category="wear_metals",
            parameter="iron_fe",
        )
        self.other_threshold = factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.other
            ),
            category="wear_metals",
            parameter="iron_fe",
        )
        self.global_threshold = factories.AnalysisThresholdFactory(
            component_type=None, category="wear_metals", parameter="iron_fe"
        )
        self.lab_user = user_for(self.lab)
        self.final_user = user_for(self.final)

    def _queryset_ids(self) -> set[int]:
        """Return the threshold ids the lab user's list would expose."""
        view = report_views.AnalysisThresholdListView()
        view.request = SimpleNamespace(user=self.lab_user)
        return set(view.get_queryset().values_list("id", flat=True))

    def test_list_scoped_to_subtree_and_globals(self) -> None:
        """The list keeps the subtree plus the global defaults."""
        self.assertEqual(
            self._queryset_ids(),
            {self.lab_threshold.id, self.final_threshold.id, self.global_threshold.id},
        )

    def test_list_excludes_foreign_organizations(self) -> None:
        """Thresholds of an unrelated organization are not listed."""
        self.assertNotIn(self.other_threshold.id, self._queryset_ids())

    def test_select_related_joins_component_type_organization(self) -> None:
        """The list joins the component type's organization to avoid N+1."""
        view = report_views.AnalysisThresholdListView()
        view.request = SimpleNamespace(user=self.lab_user)
        related = view.get_queryset().query.select_related
        self.assertIn("component_type", related)
        self.assertIn("organization", related["component_type"])

    def test_show_organization_true_for_parent(self) -> None:
        """A parent user sees the client column and filter."""
        context = list_context(report_views.AnalysisThresholdListView, self.lab_user)
        self.assertTrue(context["show_organization"])

    def test_show_organization_false_for_leaf(self) -> None:
        """A leaf user does not see the client column and filter."""
        context = list_context(report_views.AnalysisThresholdListView, self.final_user)
        self.assertFalse(context["show_organization"])

    def test_organization_filter_lists_strict_children(self) -> None:
        """The filter only offers the user's descendants."""
        filterset = filtersets.AnalysisThresholdFilter(
            queryset=models.AnalysisThreshold.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(
            filterset.filters["organization"].queryset.values_list("id", flat=True)
        )
        self.assertEqual(ids, {self.final.id})

    def test_filter_by_organization(self) -> None:
        """Filtering by a child organization narrows the thresholds."""
        filterset = filtersets.AnalysisThresholdFilter(
            {"organization": self.final.pk},
            queryset=models.AnalysisThreshold.objects.all(),
            request=SimpleNamespace(user=self.lab_user),
        )
        ids = set(filterset.qs.values_list("id", flat=True))
        self.assertEqual(ids, {self.final_threshold.id})


class ThresholdClientColumnTemplateTests(TenantSchemaTestCase):
    """The threshold list renders the Client column and filter for parent users."""

    def setUp(self) -> None:
        """Build a lab with one final client, each owning a threshold."""
        super().setUp()
        self.lab = organization_factories.OrganizationFactory(
            slug="tct-lab", kind=choices.OrganizationKind.LAB
        )
        self.final = organization_factories.OrganizationFactory(
            slug="tct-final", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.lab_user = user_for(self.lab)
        grant_permissions(self.lab_user, "view_analysisthreshold")
        self.final_user = user_for(self.final)
        grant_permissions(self.final_user, "view_analysisthreshold")
        factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.lab
            ),
            category="wear_metals",
            parameter="iron_fe",
        )
        factories.AnalysisThresholdFactory(
            component_type=equipment_factories.ComponentTypeFactory(
                organization=self.final
            ),
            category="wear_metals",
            parameter="iron_fe",
        )

    def test_parent_sees_client_filter_and_column(self) -> None:
        """A parent user gets the Client select and header."""
        self.client.force_login(self.lab_user)
        response = self.client.get(reverse("apps.reports:analysisthreshold_list"))
        self.assertContains(response, 'id="id_organization"')
        self.assertContains(response, ">Cliente<")
        self.assertContains(response, self.final.name)

    def test_leaf_sees_no_client_filter(self) -> None:
        """A leaf user gets no Client select."""
        self.client.force_login(self.final_user)
        response = self.client.get(reverse("apps.reports:analysisthreshold_list"))
        self.assertNotContains(response, 'id="id_organization"')
