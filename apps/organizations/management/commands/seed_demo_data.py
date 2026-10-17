"""Seed demo data for the MARCO tenant.

Creates a realistic multi-organization dataset so the platform can be
evaluated: the MARCO tenant with an intermediary and final clients, their
users, equipment (branches/machines/components), analysis thresholds and a
long history of reports per component (used by the component analysis page).

The command is idempotent: running it twice does not duplicate data.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal
from typing import Any, ClassVar

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from apps.equipment import choices as equipment_choices
from apps.equipment import models as equipment_models
from apps.organizations import choices as org_choices
from apps.organizations import models as org_models
from apps.reports import choices as report_choices
from apps.reports import models as report_models
from apps.users.models import User

COMPONENT_TYPES: list[tuple[str, str]] = [
    ("Motor Principal", "Motor diesel de propulsión"),
    ("Bomba Centrífuga", "Bomba de proceso de fluidos"),
    ("Compresor de Tornillo", "Compresor de aire de tornillo"),
    ("Caja Reductora", "Reductor de velocidad"),
    ("Sistema Hidráulico", "Circuito hidráulico de potencia"),
    ("Turbina de Vapor", "Turbina de vapor auxiliar"),
]

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
    ("wear_metals", "iron_fe", 75, 100, "ppm", False, "Desgaste de camisas y cilindros."),
    ("wear_metals", "copper_cu", 20, 30, "ppm", False, "Cojinetes y enfriadores."),
    ("wear_metals", "aluminum_al", 15, 25, "ppm", False, "Pistones y cojinetes de biela."),
    ("wear_metals", "lead_pb", 20, 30, "ppm", False, "Cojinetes de biela y bancada."),
    ("wear_metals", "chromium_cr", 10, 15, "ppm", False, "Anillos y válvulas."),
    ("contamination", "silicon_si", 15, 20, "ppm", False, "Ingreso de polvo por admisión."),
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


class Command(BaseCommand):
    """Seed the MARCO demo dataset."""

    help = "Seed demo organizations, equipment and historical reports for MARCO."

    MARCO_SLUG: ClassVar[str] = "marco"

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command options."""
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

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        """Create the demo data."""
        self.rng = random.Random(options["seed"])
        self.months = options["months"]

        marco = self._seed_marco()
        self._seed_organization_tree(marco)
        self._seed_users(marco)
        self._seed_component_types(marco)
        self._seed_thresholds(marco)
        self._seed_equipment_and_reports(marco)

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data seeded: "
                f"{org_models.Organization.objects.count()} organizations, "
                f"{equipment_models.Machine.objects.count()} machines, "
                f"{report_models.Report.objects.count()} reports."
            )
        )

    def _seed_marco(self) -> org_models.Organization:
        """Return (creating if needed) the MARCO tenant."""
        marco, _ = org_models.Organization.objects.get_or_create(
            slug=self.MARCO_SLUG,
            defaults={
                "name": "MARCO Peruana",
                "kind": org_choices.OrganizationKind.LAB,
                "primary_color": "#1c4ed8",
                "chart_primary": "#1c4ed8",
            },
        )
        return marco

    def _seed_organization_tree(self, marco: org_models.Organization) -> None:
        """Create one intermediary (with two final clients) and a direct final."""
        intermediary, _ = org_models.Organization.objects.get_or_create(
            slug="minera-andina",
            defaults={
                "name": "Minera Andina S.A.C.",
                "kind": org_choices.OrganizationKind.INTERMEDIARY,
                "parent": marco,
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
                "parent": marco,
                "primary_color": "#b45309",
                "chart_primary": "#b45309",
            },
        )

    def _seed_users(self, marco: org_models.Organization) -> None:
        """Create one user per role (idempotent, password: ``Demo12345!``)."""
        users = [
            ("admin@marco.pe", "Admin", "MARCO", marco, True, True),
            (
                "laboratorio@marco.pe",
                "Lab",
                "MARCO",
                marco,
                False,
                False,
            ),
            (
                "operaciones@minera-andina.pe",
                "Operaciones",
                "Andina",
                org_models.Organization.objects.get(slug="minera-andina"),
                False,
                False,
            ),
            (
                "reportes@planta-concentradora.pe",
                "Reportes",
                "Concentradora",
                org_models.Organization.objects.get(slug="planta-concentradora"),
                False,
                False,
            ),
            (
                "cliente@transportes-lima.pe",
                "Cliente",
                "Lima",
                org_models.Organization.objects.get(slug="transportes-lima"),
                False,
                False,
            ),
        ]
        for email, first_name, last_name, organization, is_staff, is_superuser in users:
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email,
                    password="Demo12345!",
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=is_staff,
                    is_superuser=is_superuser,
                )
            user.organization = organization
            user.save(update_fields=["organization"])

    def _seed_component_types(self, marco: org_models.Organization) -> None:
        """Create MARCO's own component types (the standard catalog)."""
        for name, description in COMPONENT_TYPES:
            equipment_models.ComponentType.objects.get_or_create(
                organization=marco,
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

    def _seed_thresholds(self, marco: org_models.Organization) -> None:
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

    def _seed_equipment_and_reports(self, marco: org_models.Organization) -> None:
        """Create equipment per final client and a report history per component."""
        final_orgs = list(
            marco.descendants(include_self=False).filter(
                kind=org_choices.OrganizationKind.FINAL
            )
        )
        laboratory, _ = report_models.Laboratory.objects.get_or_create(
            code="MARCO-LAB",
            defaults={"name": "Laboratorio MARCO", "created_by": None},
        )

        for org in final_orgs:
            org_types = self._ensure_types_for(org)
            for branch_index, branch_name in enumerate(BRANCHES[:2]):
                branch, _ = equipment_models.Branch.objects.get_or_create(
                    organization=org,
                    name=f"{branch_name} {org.name}",
                    defaults={"created_by": None},
                )
                machine, _ = equipment_models.Machine.objects.get_or_create(
                    organization=org,
                    branch=branch,
                    name=f"Equipo {org.slug[:6].upper()}-{branch_index + 1}",
                    defaults={
                        "serial_number": f"SN-{org.id}-{branch_index + 1}",
                        "model": self.rng.choice(MACHINE_MODELS),
                        "measurement_unit": equipment_choices.MeasurementUnit.HOURS,
                        "created_by": None,
                    },
                )
                for type_index in range(2):
                    component_type = org_types[
                        (branch_index + type_index) % len(org_types)
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
