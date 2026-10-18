"""Cross-tenant isolation tests.

The tenant schema is the hard isolation boundary of the platform: each client's
data lives in its own PostgreSQL schema. An object that exists in one tenant's
schema must therefore be invisible from another tenant — both through the ORM
and through the web views, which must answer 404 rather than leak the row.
"""

from __future__ import annotations

from django.contrib.auth.models import Permission
from django.db import connection
from django.urls import reverse
from django_tenants.utils import tenant_context

from apps.equipment import models as equipment_models
from apps.reports import factories as report_factories
from apps.reports import models as report_models
from apps.tenancy import choices
from apps.tenancy.tests.base import TenantProvisionTestCase
from apps.users import factories as user_factories
from apps.users.models import User


class CrossTenantIsolationTests(TenantProvisionTestCase):
    """No data crosses the schema boundary."""

    def setUp(self) -> None:
        """Provision a second tenant and put a report in its schema.

        The class runs inside the throwaway tenant created by
        ``TenantTestCase``; ``other`` is a separate, fully provisioned client
        with its own schema, domain, root organization and administrator.
        """
        super().setUp()
        # Teardown drops provisioned schemas and leaves the connection on
        # ``public``; select the test tenant again before touching its tables.
        connection.set_tenant(self.tenant)
        self.other = self.provision(
            slug="other",
            name="Other",
            kind=choices.TenantKind.LAB.value,
            admin_email="admin@other.pe",
            default_password="Demo12345!",
        )
        with tenant_context(self.other):
            self.foreign_report = report_factories.ReportFactory(
                lab_number="FOREIGN-0001"
            )
            self.foreign_machine = self.foreign_report.machine

    def log_in_with(self, app_label: str, *codenames: str) -> User:
        """Log in a user of the current tenant holding ``codenames``.

        Args:
            app_label: Django app label the permissions belong to.
            *codenames: Permission codenames granted to the user.

        Returns:
            The logged-in user.
        """
        user = user_factories.UserFactory()
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label=app_label, codename__in=codenames
            )
        )
        self.client.force_login(user)
        return user

    def test_other_tenant_object_is_not_reachable_by_id(self) -> None:
        """An object that exists only in another tenant is not queryable."""
        foreign_pk = self.foreign_report.pk

        self.assertFalse(report_models.Report.objects.filter(pk=foreign_pk).exists())
        with self.assertRaises(report_models.Report.DoesNotExist):
            report_models.Report.objects.get(pk=foreign_pk)

    def test_other_tenant_report_returns_404(self) -> None:
        """The report detail of another tenant answers 404 from this tenant."""
        self.log_in_with("reports", "view_report")

        response = self.client.get(
            reverse("apps.reports:report_detail", kwargs={"pk": self.foreign_report.pk})
        )

        self.assertEqual(response.status_code, 404)
        # The row was not deleted: it still lives in its own schema.
        with tenant_context(self.other):
            self.assertTrue(
                report_models.Report.objects.filter(pk=self.foreign_report.pk).exists()
            )

    def test_other_tenant_machine_returns_404(self) -> None:
        """The machine detail of another tenant answers 404 from this tenant."""
        self.log_in_with("equipment", "view_machine")

        response = self.client.get(
            reverse(
                "apps.equipment:machine_detail",
                kwargs={"pk": self.foreign_machine.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
        with tenant_context(self.other):
            self.assertTrue(
                equipment_models.Machine.objects.filter(
                    pk=self.foreign_machine.pk
                ).exists()
            )

    def test_pk_lookup_resolves_within_the_current_schema(self) -> None:
        """A pk shared with another tenant resolves to the local row.

        Primary keys are handed out per schema, so the same number identifies a
        different row in each tenant; the lookup must return the local one.
        """
        local_report = report_factories.ReportFactory(
            pk=self.foreign_report.pk, lab_number="LOCAL-0001"
        )

        fetched = report_models.Report.objects.get(pk=self.foreign_report.pk)

        self.assertEqual(fetched.pk, local_report.pk)
        self.assertEqual(fetched.lab_number, "LOCAL-0001")

    def test_local_objects_are_not_visible_from_the_other_schema(self) -> None:
        """The boundary works in both directions."""
        report_factories.ReportFactory(lab_number="LOCAL-0001")

        with tenant_context(self.other):
            self.assertFalse(
                report_models.Report.objects.filter(lab_number="LOCAL-0001").exists()
            )
            self.assertTrue(
                report_models.Report.objects.filter(
                    lab_number=self.foreign_report.lab_number
                ).exists()
            )

    def test_same_email_is_a_different_user_per_tenant(self) -> None:
        """Users belong to their tenant schema: the same email is two accounts."""
        user_factories.UserFactory(email="shared@example.com")

        with tenant_context(self.other):
            self.assertFalse(User.objects.filter(email="shared@example.com").exists())
