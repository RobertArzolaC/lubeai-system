"""Tests for the ``seed_demo_data`` management command."""

from django.core.management import call_command
from django.test import TestCase

from apps.equipment import models as equipment_models
from apps.organizations import choices, models
from apps.reports import models as report_models
from apps.users.models import User


class SeedDemoDataTests(TestCase):
    """The seed command builds the MARCO demo hierarchy and history."""

    def test_creates_hierarchy(self) -> None:
        """The intermediary and its final clients are created."""
        call_command("seed_demo_data", months=2, verbosity=0)
        self.assertTrue(
            models.Organization.objects.filter(
                slug="minera-andina", kind=choices.OrganizationKind.INTERMEDIARY
            ).exists()
        )
        self.assertTrue(
            models.Organization.objects.filter(
                slug="planta-concentradora", parent__slug="minera-andina"
            ).exists()
        )
        self.assertTrue(
            models.Organization.objects.filter(slug="transportes-lima").exists()
        )

    def test_creates_report_history_per_component(self) -> None:
        """Each component gets one report per month (historical series)."""
        call_command("seed_demo_data", months=4, verbosity=0)
        component = equipment_models.Component.objects.first()
        self.assertIsNotNone(component)
        self.assertGreaterEqual(
            report_models.Report.objects.filter(component=component).count(), 4
        )
        report = report_models.Report.objects.filter(component=component).first()
        self.assertTrue(hasattr(report, "analysis"))

    def test_is_idempotent(self) -> None:
        """Running the command twice does not duplicate data."""
        call_command("seed_demo_data", months=2, verbosity=0)
        reports = report_models.Report.objects.count()
        machines = equipment_models.Machine.objects.count()
        call_command("seed_demo_data", months=2, verbosity=0)
        self.assertEqual(report_models.Report.objects.count(), reports)
        self.assertEqual(equipment_models.Machine.objects.count(), machines)

    def test_reports_belong_to_final_organizations(self) -> None:
        """Every seeded report belongs to a final client organization."""
        call_command("seed_demo_data", months=2, verbosity=0)
        wrong = report_models.Report.objects.exclude(
            organization__kind=choices.OrganizationKind.FINAL
        ).count()
        self.assertEqual(wrong, 0)

    def test_creates_user_for_each_final_organization(self) -> None:
        """Every final client organization has at least one user."""
        call_command("seed_demo_data", months=1, verbosity=0)
        for slug in (
            "planta-concentradora",
            "planta-lixiviacion",
            "transportes-lima",
        ):
            organization = models.Organization.objects.get(slug=slug)
            self.assertTrue(
                User.objects.filter(organization=organization).exists(), slug
            )

    def test_demo_client_users_can_view_alerts_and_reports(self) -> None:
        """Demo client users have the permissions needed to evaluate."""
        call_command("seed_demo_data", months=1, verbosity=0)
        user = User.objects.get(email="reportes@planta-lixiviacion.pe")
        self.assertTrue(user.has_perm("alerts.view_alert"))
        self.assertTrue(user.has_perm("reports.view_report"))
        self.assertTrue(user.has_perm("reports.view_component_analysis"))
        self.assertTrue(user.has_perm("equipment.view_machine"))
