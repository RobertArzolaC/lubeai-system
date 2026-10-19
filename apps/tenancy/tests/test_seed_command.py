"""Tests for the per-tenant ``seed_demo_data`` command.

The demo dataset lives entirely inside one tenant schema and always hangs from
the root organization that provisioning created: the command must never build a
second root. Re-running it must not duplicate organizations, machines, reports
or users, and the same ``--seed`` must produce the same ``lab_number`` values.
"""

from __future__ import annotations

import shutil
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings
from django_tenants.utils import tenant_context

from apps.equipment import models as equipment_models
from apps.organizations import choices, models
from apps.reports import models as report_models
from apps.tenancy import branding
from apps.tenancy import choices as tenancy_choices
from apps.tenancy import models as tenancy_models
from apps.tenancy.management.commands.seed_demo_data import Command
from apps.tenancy.tests.base import TenantProvisionTestCase
from apps.users.models import User

#: Throwaway media root so branding tests never write into the project's media.
BRAND_MEDIA_ROOT = tempfile.mkdtemp(prefix="lubeai-brand-")


class SeedDemoDataTests(TenantProvisionTestCase):
    """The seed command builds the demo hierarchy under the tenant's root."""

    def setUp(self) -> None:
        """Provision the tenant the command will seed."""
        super().setUp()
        self.tenant = self.provision()
        self.root = self.root_organization()

    def root_organization(self) -> models.Organization:
        """Return the root organization inside the provisioned schema.

        Returns:
            The tenant's root organization.
        """
        with tenant_context(self.tenant):
            return models.Organization.objects.get(parent__isnull=True)

    def seed(self, **options: object) -> None:
        """Run the command against the provisioned tenant.

        Args:
            **options: Extra command options.
        """
        call_command(
            "seed_demo_data",
            schema=self.tenant.schema_name,
            verbosity=0,
            **options,
        )

    def test_reuses_the_root_organization(self) -> None:
        """Seeding does not create a second root organization."""
        self.seed(months=2)

        with tenant_context(self.tenant):
            roots = models.Organization.objects.filter(parent__isnull=True)
            self.assertEqual(roots.count(), 1)
            self.assertEqual(roots.get().pk, self.root.pk)

    def test_creates_the_client_hierarchy(self) -> None:
        """The intermediary and its final clients hang from the root."""
        self.seed(months=2)

        with tenant_context(self.tenant):
            self.assertTrue(
                models.Organization.objects.filter(
                    slug="minera-andina",
                    kind=choices.OrganizationKind.INTERMEDIARY,
                    parent=self.root,
                ).exists()
            )
            self.assertTrue(
                models.Organization.objects.filter(
                    slug="planta-concentradora", parent__slug="minera-andina"
                ).exists()
            )
            self.assertTrue(
                models.Organization.objects.filter(
                    slug="transportes-lima", parent=self.root
                ).exists()
            )

    def test_creates_a_report_history_per_component(self) -> None:
        """Each component gets one report per month (historical series)."""
        self.seed(months=4)

        with tenant_context(self.tenant):
            component = equipment_models.Component.objects.first()
            self.assertIsNotNone(component)
            self.assertGreaterEqual(
                report_models.Report.objects.filter(component=component).count(), 4
            )
            report = report_models.Report.objects.filter(component=component).first()
            self.assertTrue(hasattr(report, "analysis"))

    def test_is_idempotent(self) -> None:
        """Running the command twice does not duplicate data."""
        self.seed(months=2)
        with tenant_context(self.tenant):
            reports = report_models.Report.objects.count()
            machines = equipment_models.Machine.objects.count()
            lab_numbers = set(
                report_models.Report.objects.values_list("lab_number", flat=True)
            )

        self.seed(months=2)

        with tenant_context(self.tenant):
            self.assertEqual(report_models.Report.objects.count(), reports)
            self.assertEqual(equipment_models.Machine.objects.count(), machines)
            self.assertEqual(
                set(report_models.Report.objects.values_list("lab_number", flat=True)),
                lab_numbers,
            )

    def test_reuses_the_provisioned_component_types(self) -> None:
        """The catalog created by provisioning is extended, never duplicated."""
        with tenant_context(self.tenant):
            provisioned = equipment_models.ComponentType.objects.filter(
                organization=self.root
            ).count()

        self.seed(months=1)

        with tenant_context(self.tenant):
            self.assertEqual(
                equipment_models.ComponentType.objects.filter(
                    organization=self.root
                ).count(),
                provisioned,
            )

    def test_reports_belong_to_final_organizations(self) -> None:
        """Every seeded report belongs to a final client organization."""
        self.seed(months=2)

        with tenant_context(self.tenant):
            wrong = report_models.Report.objects.exclude(
                organization__kind=choices.OrganizationKind.FINAL
            ).count()
            self.assertEqual(wrong, 0)

    def test_derives_root_identities_from_the_tenant(self) -> None:
        """Seeding another tenant never creates MARCO-branded accounts."""
        self.seed(months=1)

        with tenant_context(self.tenant):
            self.assertEqual(self.root.slug, "acme")
            self.assertFalse(User.objects.filter(email="admin@marco.pe").exists())
            self.assertFalse(User.objects.filter(email="laboratorio@marco.pe").exists())
            self.assertTrue(
                User.objects.filter(email="admin@acme.pe", is_superuser=True).exists()
            )
            self.assertTrue(User.objects.filter(email="laboratorio@acme.pe").exists())
            self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
            self.assertFalse(
                report_models.Laboratory.objects.filter(code="MARCO-LAB").exists()
            )
            self.assertTrue(
                report_models.Laboratory.objects.filter(code="ACME-LAB").exists()
            )

    def test_creates_a_user_for_each_final_organization(self) -> None:
        """Every final client organization has at least one user."""
        self.seed(months=1)

        with tenant_context(self.tenant):
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
        self.seed(months=1)

        with tenant_context(self.tenant):
            user = User.objects.get(email="reportes@planta-lixiviacion.pe")
            self.assertTrue(user.has_perm("alerts.view_alert"))
            self.assertTrue(user.has_perm("reports.view_report"))
            self.assertTrue(user.has_perm("reports.view_component_analysis"))
            self.assertTrue(user.has_perm("equipment.view_machine"))

    def test_machine_and_component_options_extend_the_history(self) -> None:
        """``--machines`` and ``--components`` widen the seeded dataset."""
        self.seed(months=1, machines=3, components=4)

        with tenant_context(self.tenant):
            self.assertEqual(equipment_models.Machine.objects.count(), 18)
            self.assertEqual(equipment_models.Component.objects.count(), 72)

    def test_seed_creates_long_component_history(self) -> None:
        """Each seeded component keeps a 36-month monthly report history."""
        parser = Command().create_parser("manage.py", "seed_demo_data")
        self.assertEqual(parser.parse_args([]).months, 36)

        self.seed(months=36)

        with tenant_context(self.tenant):
            component_ids = list(
                equipment_models.Component.objects.values_list("pk", flat=True)
            )
            self.assertGreater(len(component_ids), 0)
            for component_id in component_ids:
                self.assertGreaterEqual(
                    report_models.Report.objects.filter(
                        component_id=component_id
                    ).count(),
                    36,
                )

    def test_requires_a_provisioned_tenant(self) -> None:
        """A schema without a root organization cannot be seeded."""
        connection.set_schema_to_public()
        bare = tenancy_models.Tenant.objects.create(
            name="Bare", slug="bare", kind="lab"
        )
        self.addCleanup(self.drop_tenant, bare)

        with self.assertRaises(CommandError):
            call_command("seed_demo_data", schema="bare", verbosity=0)


@override_settings(MEDIA_ROOT=BRAND_MEDIA_ROOT)
class KnownBrandSeedTests(TenantProvisionTestCase):
    """Seeding a known client leaves its demo carrying the real brand."""

    tenant_name = "Brand tests"

    @classmethod
    def setUpClass(cls) -> None:
        """Drop the throwaway media root once the class is done."""
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, BRAND_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        """Provision the unbranded tenant reused by the default test."""
        super().setUp()
        self.tenant = self.provision()

    def seed(self, **options: object) -> None:
        """Run the seed command against the throwaway tenant.

        Args:
            **options: Extra command options.
        """
        call_command(
            "seed_demo_data",
            schema=self.tenant.schema_name,
            verbosity=0,
            **options,
        )

    def seed_marco(self) -> models.Organization:
        """Provision and seed the MARCO tenant.

        Returns:
            The MARCO root organization read inside its schema.
        """
        tenant = self.provision(
            slug="marco",
            name="MARCO Peruana",
            kind=tenancy_choices.TenantKind.LAB.value,
            admin_email="admin@marco.pe",
        )
        call_command("seed_demo_data", schema=tenant.slug, months=1, verbosity=0)
        with tenant_context(tenant):
            return models.Organization.objects.get(parent__isnull=True)

    def test_known_brand_reaches_the_tenant_and_its_root(self) -> None:
        """The tenant and its root organization carry the real palette."""
        root = self.seed_marco()
        tenant = tenancy_models.Tenant.objects.get(slug="marco")
        brand = branding.KNOWN_BRANDS["marco"]

        for slot, value in brand.items():
            self.assertEqual(getattr(tenant, slot), value, slot)
            self.assertEqual(getattr(root, slot), value, slot)

    def test_known_brand_installs_the_logo(self) -> None:
        """The packaged logo ends up on the tenant and on the root."""
        root = self.seed_marco()
        tenant = tenancy_models.Tenant.objects.get(slug="marco")

        self.assertTrue(tenant.logo)
        self.assertTrue(tenant.logo.storage.exists(tenant.logo.name))
        self.assertEqual(root.logo.name, tenant.logo.name)

    def test_unknown_brand_keeps_the_platform_defaults(self) -> None:
        """A tenant with no known brand is not branded by seeding."""
        self.seed(months=1)

        with tenant_context(self.tenant):
            root = models.Organization.objects.get(parent__isnull=True)
            self.assertEqual(root.primary_color, "")
            self.assertFalse(root.logo)
