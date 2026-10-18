"""Seed demo data into one tenant schema.

Creates a realistic multi-organization dataset so the platform can be evaluated:
the tenant's root organization, an intermediary and final clients, their users,
equipment (branches/machines/components), analysis thresholds and a long history
of reports per component (used by the component analysis page).

The command works **inside** the tenant schema and reuses the root organization
that ``provision_tenant`` created: it never builds a second root. The command is
idempotent — running it twice does not duplicate data.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, tenant_context

from apps.equipment import choices as equipment_choices
from apps.equipment import models as equipment_models
from apps.organizations import choices as org_choices
from apps.organizations import models as org_models
from apps.reports import choices as report_choices
from apps.reports import models as report_models
from apps.tenancy import constants
from apps.tenancy import models as tenancy_models
from apps.users.models import User

COMPONENT_TYPES = constants.DEFAULT_COMPONENT_TYPES

LUBRICANTS: list[str] = [
    "Aceite motor SAE 15W-40 API CI-4",
    "Aceite hidráulico ISO VG 46",
    "Aceite de engranajes ISO VG 220",
    "Aceite de turbina ISO VG 32",
    "Aceite compresor ISO VG 100",
    "Aceite motor marino TBN 30 (SAE 40)",
]

BRANCHES: list[str] = [
    "Planta Norte",
    "Planta Sur",
    "Terminal Portuario",
]

MACHINE_MODELS: list[str] = [
    "Caterpillar 3512C",
    "Cummins KTA19",
    "Wärtsilä 8L20",
    "MAN B&W 6S50MC",
    "Siemens 1LA7",
]

# (normal, caution, critical) ranges for the main monitored parameters.
PARAMETER_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "iron_fe": {"normal": (8, 40), "caution": (50, 95), "critical": (105, 190)},
    "copper_cu": {"normal": (1, 18), "caution": (22, 45), "critical": (55, 140)},
    "aluminum_al": {"normal": (1, 12), "caution": (18, 38), "critical": (45, 85)},
    "chromium_cr": {"normal": (0, 4), "caution": (8, 14), "critical": (16, 40)},
    "lead_pb": {"normal": (0, 12), "caution": (18, 35), "critical": (45, 95)},
    "silicon_si": {"normal": (2, 12), "caution": (18, 45), "critical": (55, 140)},
    "sodium_na": {"normal": (1, 20), "caution": (35, 80), "critical": (95, 220)},
    "potassium_k": {"normal": (0, 5), "caution": (8, 14), "critical": (18, 40)},
    "zinc_zn": {"normal": (900, 1400), "caution": (650, 780), "critical": (300, 580)},
    "phosphorus_p": {
        "normal": (800, 1300),
        "caution": (720, 790),
        "critical": (350, 680),
    },
    "magnesium_mg": {"normal": (200, 900), "caution": (100, 180), "critical": (20, 90)},
    "calcium_ca": {
        "normal": (1800, 3000),
        "caution": (900, 1400),
        "critical": (300, 800),
    },
}

# Global thresholds seeded so the component analysis uses DB values.
THRESHOLDS: list[tuple[str, str, float, float, str, bool, str]] = [
    (
        "wear_metals",
        "iron_fe",
        75,
        100,
        "ppm",
        False,
        "Desgaste de camisas y cilindros.",
    ),
    ("wear_metals", "copper_cu", 20, 30, "ppm", False, "Cojinetes y enfriadores."),
    (
        "wear_metals",
        "aluminum_al",
        15,
        25,
        "ppm",
        False,
        "Pistones y cojinetes de biela.",
    ),
    ("wear_metals", "lead_pb", 20, 30, "ppm", False, "Cojinetes de biela y bancada."),
    ("wear_metals", "chromium_cr", 10, 15, "ppm", False, "Anillos y válvulas."),
    (
        "contamination",
        "silicon_si",
        15,
        20,
        "ppm",
        False,
        "Ingreso de polvo por admisión.",
    ),
    ("contamination", "sodium_na", 30, 50, "ppm", False, "Ingreso de refrigerante."),
    ("contamination", "potassium_k", 10, 15, "ppm", False, "Ingreso de refrigerante."),
    ("additives", "zinc_zn", 800, 600, "ppm", True, "Aditivo antidesgaste (ZDDP)."),
    ("additives", "phosphorus_p", 900, 700, "ppm", True, "Aditivo antidesgaste."),
    ("additives", "magnesium_mg", 1800, 1500, "ppm", True, "Detergente/dispersante."),
    ("additives", "calcium_ca", 2000, 1500, "ppm", True, "Detergente/dispersante."),
]

RECOMMENDATIONS: list[str] = [
    "Continuar monitoreo según plan.",
    "Programar cambio de aceite y filtros en la próxima parada.",
    "Inspeccionar cojinetes ante el incremento de metales de desgaste.",
    "Revisar sellos y sistema de refrigeración.",
    "Solicitar análisis de confirmación en 100 horas.",
]

CONDITIONS: list[str] = [
    report_choices.ReportCondition.NORMAL,
    report_choices.ReportCondition.CAUTION,
    report_choices.ReportCondition.CRITICAL,
]

# Permissions granted to the demo users so they can evaluate the UI
# (without them the scoped users would get a 403 on reports/alerts).
DEMO_VIEW_PERMISSIONS: list[str] = [
    "view_report",
    "view_component_analysis",
    "view_analysisthreshold",
    "view_alert",
    "view_machine",
    "view_branch",
    "view_componenttype",
]


class Command(BaseCommand):
    """Seed the demo dataset of one tenant."""

    help = "Seed demo organizations, equipment and historical reports for a tenant."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command options.

        Args:
            parser: The command's argument parser.
        """
        parser.add_argument(
            "--schema",
            default=None,
            help=(
                "Tenant schema to seed. Defaults to the schema already selected "
                "on the connection."
            ),
        )
        parser.add_argument(
            "--months",
            type=int,
            default=18,
            help="Number of monthly samples per component (default: 18).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible data.",
        )
        parser.add_argument(
            "--machines",
            type=int,
            default=1,
            help="Number of machines per branch (default: 1).",
        )
        parser.add_argument(
            "--components",
            type=int,
            default=2,
            help="Number of components per machine (default: 2).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Create the demo data inside the selected tenant schema.

        The transaction is opened **inside** ``tenant_context``: easy-audit
        registers its CRUD events with ``transaction.on_commit``, so committing
        after the schema has been restored would write into the wrong schema.

        Args:
            *args: Unused positional arguments.
            **options: Parsed management options.

        Raises:
            CommandError: If no tenant is selected or its root organization is
                missing (the tenant has not been provisioned).
        """
        self.rng = random.Random(options["seed"])
        self.months = options["months"]
        self.machines = options["machines"]
        self.components = options["components"]

        tenant = self._resolve_tenant(options["schema"])
        with tenant_context(tenant), transaction.atomic():
            root = self._root_organization(tenant)
            self._seed_organization_tree(root)
            self._seed_users(root)
            self._seed_component_types(root)
            self._seed_thresholds(root)
            self._seed_equipment_and_reports(root)

            self.stdout.write(
                self.style.SUCCESS(
                    "Demo data seeded: "
                    f"{org_models.Organization.objects.count()} organizations, "
                    f"{equipment_models.Machine.objects.count()} machines, "
                    f"{report_models.Report.objects.count()} reports."
                )
            )

    def _resolve_tenant(self, schema_name: str | None) -> tenancy_models.Tenant:
        """Return the tenant whose schema the command will seed.

        Args:
            schema_name: Explicit schema name, or ``None`` to use the schema
                already selected on the connection.

        Returns:
            The tenant to seed.

        Raises:
            CommandError: If the schema does not exist or no tenant is selected.
        """
        if schema_name:
            tenant = tenancy_models.Tenant.objects.filter(
                schema_name=schema_name
            ).first()
            if tenant is None:
                raise CommandError(f"No tenant with schema '{schema_name}'.")
            return tenant

        tenant = getattr(connection, "tenant", None)
        if tenant is None or tenant.schema_name == get_public_schema_name():
            raise CommandError(
                "Select a tenant with --schema or run the command inside one."
            )
        return tenant

    def _root_organization(
        self, tenant: tenancy_models.Tenant
    ) -> org_models.Organization:
        """Return the tenant's root organization.

        Args:
            tenant: Tenant being seeded.

        Returns:
            The root organization created by ``provision_tenant``.

        Raises:
            CommandError: If the tenant has no root organization yet.
        """
        root = org_models.Organization.objects.filter(parent__isnull=True).first()
        if root is None:
            raise CommandError(
                f"Tenant '{tenant.slug}' has no root organization; "
                "run provision_tenant first."
            )
        return root

    def _seed_organization_tree(self, root: org_models.Organization) -> None:
        """Create one intermediary (with two final clients) and a direct final."""
        intermediary, _ = org_models.Organization.objects.get_or_create(
            slug="minera-andina",
            defaults={
                "name": "Minera Andina S.A.C.",
                "kind": org_choices.OrganizationKind.INTERMEDIARY,
                "parent": root,
                "primary_color": "#0f766e",
                "chart_primary": "#0f766e",
                "chart_danger": "#b91c1c",
                "created_by": None,
            },
        )
        for slug, name in [
            ("planta-concentradora", "Planta Concentradora"),
            ("planta-lixiviacion", "Planta de Lixiviación"),
        ]:
            org_models.Organization.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "kind": org_choices.OrganizationKind.FINAL,
                    "parent": intermediary,
                },
            )

        org_models.Organization.objects.get_or_create(
            slug="transportes-lima",
            defaults={
                "name": "Transportes Lima S.A.",
                "kind": org_choices.OrganizationKind.FINAL,
                "parent": root,
                "primary_color": "#b45309",
                "chart_primary": "#b45309",
            },
        )

    def _seed_users(self, root: org_models.Organization) -> None:
        """Create one user per role (idempotent, demo password).

        The root users derive their identity from the tenant's root
        organization, so seeding any tenant never produces another client's
        branded accounts (and never a second superuser: the ``admin@<slug>``
        account is the one ``provision_tenant`` already created).
        """

        def organization(slug: str) -> org_models.Organization:
            return org_models.Organization.objects.get(slug=slug)

        users = [
            (f"admin@{root.slug}.pe", "Admin", root.name, root, True, True),
            (f"laboratorio@{root.slug}.pe", "Lab", root.name, root, False, False),
            (
                "operaciones@minera-andina.pe",
                "Operaciones",
                "Andina",
                organization("minera-andina"),
                False,
                False,
            ),
            (
                "reportes@planta-concentradora.pe",
                "Reportes",
                "Concentradora",
                organization("planta-concentradora"),
                False,
                False,
            ),
            (
                "reportes@planta-lixiviacion.pe",
                "Reportes",
                "Lixiviacion",
                organization("planta-lixiviacion"),
                False,
                False,
            ),
            (
                "cliente@transportes-lima.pe",
                "Cliente",
                "Lima",
                organization("transportes-lima"),
                False,
                False,
            ),
        ]

        permissions = Permission.objects.filter(codename__in=DEMO_VIEW_PERMISSIONS)
        for email, first_name, last_name, user_org, is_staff, is_superuser in users:
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email,
                    password=constants.DEMO_PASSWORD,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=is_staff,
                    is_superuser=is_superuser,
                )
            user.organization = user_org
            user.save(update_fields=["organization"])
            user.user_permissions.add(*permissions)

    def _seed_component_types(self, root: org_models.Organization) -> None:
        """Create the tenant's own component types (the standard catalog)."""
        for name, description in COMPONENT_TYPES:
            equipment_models.ComponentType.objects.get_or_create(
                organization=root,
                name=name,
                defaults={"description": description, "created_by": None},
            )

    def _ensure_types_for(
        self, organization: org_models.Organization
    ) -> list[equipment_models.ComponentType]:
        """Return (creating if needed) the standard types for an organization."""
        types: list[equipment_models.ComponentType] = []
        for name, description in COMPONENT_TYPES:
            component_type, _ = equipment_models.ComponentType.objects.get_or_create(
                organization=organization,
                name=name,
                defaults={"description": description, "created_by": None},
            )
            types.append(component_type)
        return types

    def _seed_thresholds(self, root: org_models.Organization) -> None:
        """Create the global analysis thresholds."""
        for category, parameter, warning, critical, unit, inverse, source in THRESHOLDS:
            report_models.AnalysisThreshold.objects.get_or_create(
                component_type=None,
                category=category,
                parameter=parameter,
                defaults={
                    "warning_limit": warning,
                    "critical_limit": critical,
                    "unit": unit,
                    "is_inverse": inverse,
                    "wear_source_description": source,
                    "created_by": None,
                },
            )

    def _seed_equipment_and_reports(self, root: org_models.Organization) -> None:
        """Create equipment per final client and a report history per component."""
        final_orgs = list(
            root.descendants(include_self=False).filter(
                kind=org_choices.OrganizationKind.FINAL
            )
        )
        laboratory, _ = report_models.Laboratory.objects.get_or_create(
            code=f"{root.slug[:8].upper()}-LAB",
            defaults={"name": f"Laboratorio {root.name}", "created_by": None},
        )

        for org in final_orgs:
            org_types = self._ensure_types_for(org)
            for branch_index, branch_name in enumerate(BRANCHES[:2]):
                branch, _ = equipment_models.Branch.objects.get_or_create(
                    organization=org,
                    name=f"{branch_name} {org.name}",
                    defaults={"created_by": None},
                )
                for machine_index in range(self.machines):
                    machine, _ = equipment_models.Machine.objects.get_or_create(
                        organization=org,
                        branch=branch,
                        name=(
                            f"Equipo {org.slug[:6].upper()}-"
                            f"{branch_index + 1}-{machine_index + 1}"
                        ),
                        defaults={
                            "serial_number": (
                                f"SN-{org.id}-{branch_index + 1}-{machine_index + 1}"
                            ),
                            "model": self.rng.choice(MACHINE_MODELS),
                            "measurement_unit": (
                                equipment_choices.MeasurementUnit.HOURS
                            ),
                            "created_by": None,
                        },
                    )
                    for type_index in range(self.components):
                        component_type = org_types[
                            (branch_index + machine_index + type_index) % len(org_types)
                        ]
                        component, _ = equipment_models.Component.objects.get_or_create(
                            machine=machine,
                            type=component_type,
                            defaults={"created_by": None},
                        )
                        self._seed_component_history(
                            organization=org,
                            machine=machine,
                            component=component,
                            laboratory=laboratory,
                        )

    def _seed_component_history(
        self,
        organization: org_models.Organization,
        machine: equipment_models.Machine,
        component: equipment_models.Component,
        laboratory: report_models.Laboratory,
    ) -> None:
        """Create the monthly report history for a single component."""
        start = timezone.localdate() - timedelta(days=30 * self.months)
        # Each component has a base condition trend (some degrade over time).
        base_condition = self.rng.choice(CONDITIONS)
        degrade = self.rng.random() < 0.5

        for month in range(self.months):
            sample_date = start + timedelta(days=30 * month)
            condition = self._evolve_condition(base_condition, month, degrade)
            lab_number = f"{organization.slug[:8].upper()}-{machine.id}-{component.id}-{sample_date:%Y%m}"
            report, created = report_models.Report.objects.get_or_create(
                lab_number=lab_number,
                defaults={
                    "organization": organization,
                    "laboratory": laboratory,
                    "machine": machine,
                    "component": component,
                    "lubricant": self.rng.choice(LUBRICANTS),
                    "machine_hours": 500 * month + self.rng.randint(0, 400),
                    "sample_date": sample_date,
                    "reception_date": sample_date + timedelta(days=1),
                    "report_date": sample_date + timedelta(days=3),
                    "status": report_choices.ReportStatus.REVIEWED,
                    "condition": condition,
                    "recommendations": self.rng.choice(RECOMMENDATIONS),
                    "created_by": None,
                },
            )
            if not created and hasattr(report, "analysis"):
                continue
            self._upsert_analysis(report, condition, month)

    def _evolve_condition(self, base: str, month: int, degrade: bool) -> str:
        """Return the condition for a given month (optionally degrading)."""
        if degrade:
            if month < self.months * 0.5:
                return report_choices.ReportCondition.NORMAL
            if month < self.months * 0.8:
                return report_choices.ReportCondition.CAUTION
            return report_choices.ReportCondition.CRITICAL
        return base

    def _upsert_analysis(
        self, report: report_models.Report, condition: str, month: int
    ) -> None:
        """Create or update the LabAnalysis for a report."""
        values = self._analysis_values(condition)
        values.update(
            {
                "water_crackle": "NEGATIVO" if condition == "NORMAL" else "POSITIVO",
                "water_distillation": Decimal("0.020"),
                "viscosity_40c": Decimal(str(round(self.rng.uniform(80, 110), 2))),
                "viscosity_100c": Decimal(str(round(self.rng.uniform(11, 15), 2))),
                "viscosity_index": self.rng.randint(90, 120),
                "tbn": Decimal(str(round(self.rng.uniform(5, 11), 2))),
                "tan": Decimal(str(round(self.rng.uniform(0.5, 2.5), 2))),
                "oxidation": Decimal(str(round(self.rng.uniform(5, 25), 3))),
                "nitration": Decimal(str(round(self.rng.uniform(2, 12), 3))),
                "sulfation": Decimal(str(round(self.rng.uniform(2, 14), 3))),
                "glycol": Decimal("0.000"),
                "fuel_dilution": Decimal(str(round(self.rng.uniform(0, 3), 3))),
                "water_ftir": Decimal(str(round(self.rng.uniform(0, 1.5), 3))),
                "pq_index": self.rng.randint(5, 120),
                "particle_count_iso": self.rng.choice(
                    ["18/16/13", "19/17/14", "20/18/15", "21/19/16"]
                ),
                "dispersancy": "BUE" if condition == "NORMAL" else "REG",
                "spot_test": "Mancha difusa",
                "visual_appearance": "Claro" if condition == "NORMAL" else "Oscuro",
                "created_by": report.created_by,
                "updated_by": report.updated_by,
            }
        )
        report_models.LabAnalysis.objects.update_or_create(
            report=report, defaults=values
        )

    def _analysis_values(self, condition: str) -> dict[str, Any]:
        """Return the parameter values for a given condition."""
        values: dict[str, Any] = {}
        for parameter, ranges in PARAMETER_RANGES.items():
            low, high = ranges[condition.lower()]
            values[parameter] = int(self.rng.uniform(low, high))
        return values
