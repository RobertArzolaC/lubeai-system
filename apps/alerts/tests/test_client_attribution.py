"""Tests for client attribution on the alert list."""

from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.alerts import factories, filtersets, models
from apps.alerts import views as alert_views
from apps.equipment import factories as equipment_factories
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


def user_for(organization):
    """Return a persisted user belonging to ``organization``."""
    user = user_factories.UserFactory()
    user.organization = organization
    user.save(update_fields=["organization"])
    return user


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given alerts permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="alerts",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)


class AlertClientFilterTests(TestCase):
    """The alert filter accepts an organization and hides it for leaf users."""

    def setUp(self) -> None:
        """Build a lab with a final client and an unrelated tenant."""
        self.lab = organization_factories.OrganizationFactory(
            slug="ac-lab", kind=choices.OrganizationKind.LAB
        )
        self.child = organization_factories.OrganizationFactory(
            slug="ac-child", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        self.other = organization_factories.OrganizationFactory(
            slug="ac-other", kind=choices.OrganizationKind.LAB
        )
        machine = equipment_factories.MachineFactory(organization=self.child)
        self.alert = factories.AlertFactory(
            machine=machine, organization=self.child, dedup_key="ac-one"
        )
        self.other_alert = factories.AlertFactory(
            organization=self.other, dedup_key="ac-two"
        )
        self.user = user_for(self.lab)

    def test_filter_by_organization(self) -> None:
        """Filtering by organization narrows the alerts."""
        request = SimpleNamespace(user=self.user)
        filtered = filtersets.AlertFilter(
            {"organization": self.child.pk},
            queryset=models.Alert.objects.all(),
            request=request,
        ).qs
        self.assertIn(self.alert, filtered)
        self.assertNotIn(self.other_alert, filtered)

    def test_organization_filter_hidden_for_leaf(self) -> None:
        """A leaf user gets no organization filter."""
        request = SimpleNamespace(user=user_for(self.child))
        filterset = filtersets.AlertFilter(
            queryset=models.Alert.objects.all(), request=request
        )
        self.assertNotIn("organization", filterset.filters)

    def test_organization_filter_choices_are_scoped(self) -> None:
        """The choices are limited to the visible subtree."""
        request = SimpleNamespace(user=self.user)
        filterset = filtersets.AlertFilter(
            queryset=models.Alert.objects.all(), request=request
        )
        ids = set(
            filterset.filters["organization"].queryset.values_list("id", flat=True)
        )
        self.assertEqual(ids, {self.lab.id, self.child.id})


class AlertClientColumnTests(TestCase):
    """The alert list exposes the organization join and the client column."""

    def setUp(self) -> None:
        """Build a lab with a final client owning one alert."""
        self.lab = organization_factories.OrganizationFactory(
            slug="acc-lab", kind=choices.OrganizationKind.LAB
        )
        self.child = organization_factories.OrganizationFactory(
            slug="acc-child", kind=choices.OrganizationKind.FINAL, parent=self.lab
        )
        machine = equipment_factories.MachineFactory(organization=self.child)
        self.alert = factories.AlertFactory(
            machine=machine, organization=self.child, dedup_key="acc-one"
        )

    def test_alert_list_selects_organization(self) -> None:
        """The alert list joins the organization to avoid N+1 queries."""
        related = alert_views.AlertListView().get_queryset().query.select_related
        self.assertIn("organization", related)

    def test_parent_sees_column_and_filter(self) -> None:
        """A parent user gets the organization filter and the client name."""
        user = user_for(self.lab)
        grant_permissions(user, "view_alert")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertContains(response, 'name="organization"')
        self.assertContains(response, self.child.name)

    def test_leaf_does_not_see_column_or_filter(self) -> None:
        """A leaf user sees the plain list, without the client column."""
        user = user_for(self.child)
        grant_permissions(user, "view_alert")
        self.client.force_login(user)
        response = self.client.get(reverse("apps.alerts:alert_list"))
        self.assertNotContains(response, 'name="organization"')
