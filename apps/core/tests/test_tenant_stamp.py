"""Tests for the organization stamping in ``UserStampMixin``."""

from types import SimpleNamespace

from apps.core.mixins.forms import UserStampMixin
from apps.core.tests.base import TenantSchemaTestCase
from apps.equipment import factories as equipment_factories
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.reports import models as report_models
from apps.users import factories as user_factories


class AssignOrganizationTests(TenantSchemaTestCase):
    """Created tenant-owned instances inherit the right organization."""

    def setUp(self) -> None:
        """Build two organizations and a scoped user."""
        super().setUp()
        self.organization = organization_factories.OrganizationFactory(
            slug="stamp-a", kind=choices.OrganizationKind.LAB
        )
        self.other = organization_factories.OrganizationFactory(
            slug="stamp-b", kind=choices.OrganizationKind.LAB
        )
        self.user = user_factories.UserFactory()
        self.user.organization = self.organization
        self.user.save(update_fields=["organization"])
        self.mixin = UserStampMixin()
        self.mixin.request = SimpleNamespace(user=self.user)

    def test_report_inherits_machine_organization(self) -> None:
        """A report takes the organization from its machine."""
        machine = equipment_factories.MachineFactory(organization=self.other)
        report = report_models.Report(machine=machine)
        self.mixin._assign_organization(report)
        self.assertEqual(report.organization_id, self.other.id)

    def test_machine_uses_user_organization(self) -> None:
        """A machine without a parent attribute uses the user's organization."""
        from apps.equipment import models as equipment_models

        machine = equipment_models.Machine()
        self.mixin._assign_organization(machine)
        self.assertEqual(machine.organization_id, self.organization.id)

    def test_existing_organization_is_not_overwritten(self) -> None:
        """An already assigned organization is preserved."""
        report = report_models.Report(organization=self.other)
        self.mixin._assign_organization(report)
        self.assertEqual(report.organization_id, self.other.id)
