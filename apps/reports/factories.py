import factory
from django.utils import timezone

from apps.equipment import factories as equipment_factories
from apps.reports import choices, models
from apps.users import factories as user_factories

MARINE_LABORATORIES = [
    ("Intertek Marine Services", "INT-MAR-01"),
    ("SGS Oil Condition Monitoring", "SGS-OCM-01"),
    ("Bureau Veritas Marítimo", "BV-MAR-01"),
    ("Laboratorio Naval del Pacífico", "LNP-01"),
    ("Centro de Análisis de Lubricantes Marinos", "CALM-01"),
]

LUBRICANTS = [
    "Aceite de motor marino TBN 30 (SAE 40)",
    "Aceite hidráulico ISO VG 46",
    "Aceite de engranajes ISO VG 220",
    "Aceite de turbina ISO VG 32",
    "Aceite de motor SAE 15W-40 API CI-4",
    "Aceite de compresor ISO VG 100",
]

NOTES = [
    "Muestra tomada en puerto tras 500 horas de navegación.",
    "Muestra extraída durante mantenimiento programado en dique seco.",
    "Régimen de navegación continuo; sin novedades operativas.",
    "Muestra tomada tras maniobra prolongada en puerto.",
    "Equipo operando con carga parcial al momento del muestreo.",
]

RECOMMENDATIONS = [
    "Realizar cambio de aceite y filtros en la próxima escala.",
    "Inspeccionar cojinetes ante el incremento de metales de desgaste.",
    "Verificar sellos del separador de combustible.",
    "Monitorear la tendencia de hierro en las próximas 250 horas.",
    "Programar análisis de vibraciones complementario.",
    "Revisar el sistema de refrigeración para descartar ingreso de agua.",
]

ACTIONS_REQUIRED = [
    "Solicitar análisis de confirmación en 100 horas.",
    "Programar inspección visual del componente.",
    "Sin acción inmediata; continuar monitoreo.",
    "Sustituir filtro y remuestrear.",
]

OTHERS = [
    "Sin observaciones adicionales.",
    "Se adjunta tendencia histórica del componente.",
    "Equipo en condición operativa normal.",
]

VISUAL_APPEARANCES = [
    "Claro",
    "Ligeramente turbio",
    "Oscuro",
    "Contaminado",
    "Normal",
    "Con sedimento",
]

DISPERSANCY_RATINGS = ["BUE", "REG", "MALA", ""]

SPOT_TESTS = ["Sin mancha", "Mancha difusa", "Mancha definida", ""]

WEAR_SOURCES = [
    "Desgaste de camisas, anillos y bloque del motor principal.",
    "Desgaste de cojinetes, bujes y enfriadores de aceite.",
    "Contaminación por agua de mar en el sistema de lubricación.",
    "Agotamiento de aditivos por combustibles con alto azufre.",
    "Oxidación térmica por operación a alta temperatura.",
    "Ingreso de arena o sal por la admisión de aire.",
    "Partículas ferrosas gruesas asociadas a desgaste severo.",
]

LABORATORY_DESCRIPTIONS = [
    "Laboratorio especializado en análisis de lubricantes marinos.",
    "Monitoreo de condición de aceites para flotas navales.",
    "Análisis fisicoquímico y de metales de desgaste.",
    "Servicios de diagnóstico predictivo para maquinaria marina.",
]


class LaboratoryFactory(factory.django.DjangoModelFactory):
    """Factory for maritime laboratory test instances."""

    class Meta:
        model = models.Laboratory

    name = factory.Sequence(
        lambda n: MARINE_LABORATORIES[n % len(MARINE_LABORATORIES)][0]
    )
    code = factory.Sequence(
        lambda n: (
            MARINE_LABORATORIES[n % len(MARINE_LABORATORIES)][1]
            if n < len(MARINE_LABORATORIES)
            else f"LAB-MAR-{n + 1:03d}"
        )
    )
    description = factory.Sequence(
        lambda n: LABORATORY_DESCRIPTIONS[n % len(LABORATORY_DESCRIPTIONS)]
    )
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class ReportFactory(factory.django.DjangoModelFactory):
    """Factory for maritime report test instances."""

    class Meta:
        model = models.Report

    laboratory = factory.SubFactory(LaboratoryFactory)
    machine = factory.SubFactory(equipment_factories.MachineFactory)
    component = factory.SubFactory(
        equipment_factories.ComponentFactory,
        machine=factory.SelfAttribute("..machine"),
    )
    lab_number = factory.Sequence(lambda n: f"INFORME-{n:06d}")
    lubricant = factory.Sequence(lambda n: LUBRICANTS[n % len(LUBRICANTS)])
    lubricant_hours = factory.Faker("random_int", min=0, max=5000)
    lubricant_kms = factory.Faker("random_int", min=0, max=50000)
    machine_hours = factory.Faker("random_int", min=0, max=10000)
    machine_kms = factory.Faker("random_int", min=0, max=100000)
    serial_number_code = factory.Sequence(lambda n: f"SER-{n:08d}")
    sample_date = factory.Faker("date_between", start_date="-1y", end_date="today")
    per_number = factory.Sequence(lambda n: f"PER-{n:05d}")
    reception_date = factory.LazyAttribute(
        lambda obj: (
            obj.sample_date + timezone.timedelta(days=1) if obj.sample_date else None
        )
    )
    status = factory.Iterator([choice[0] for choice in choices.ReportStatus.choices])
    condition = factory.Iterator(
        [choice[0] for choice in choices.ReportCondition.choices]
    )
    notes = factory.Sequence(lambda n: NOTES[n % len(NOTES)])
    report_date = factory.LazyAttribute(
        lambda obj: (
            obj.reception_date + timezone.timedelta(days=2)
            if obj.reception_date
            else None
        )
    )
    filter_change = factory.Faker("random_element", elements=["SÍ", "NO", ""])
    oil_change = factory.Faker("random_element", elements=["SÍ", "NO", ""])
    others = factory.Sequence(lambda n: OTHERS[n % len(OTHERS)])
    recommendations = factory.Sequence(
        lambda n: RECOMMENDATIONS[n % len(RECOMMENDATIONS)]
    )
    action_required = factory.Sequence(
        lambda n: ACTIONS_REQUIRED[n % len(ACTIONS_REQUIRED)]
    )
    sampling_type = factory.Faker("random_element", elements=["INSP", "PORT", ""])
    pm_position = factory.Faker(
        "random_element", elements=["PRE-PM", "POST-PM", "INSP"]
    )
    turnaround_days = factory.Faker("random_int", min=1, max=10)
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class LabAnalysisFactory(factory.django.DjangoModelFactory):
    """Factory for creating LabAnalysis test instances with realistic values."""

    class Meta:
        model = models.LabAnalysis

    report = factory.SubFactory(ReportFactory)
    created_by = factory.SelfAttribute("report.created_by")
    updated_by = factory.SelfAttribute("report.updated_by")

    # Water Tests
    water_crackle = factory.Faker(
        "random_element", elements=["NEGATIVO", "POSITIVO", ""]
    )
    water_distillation = factory.Faker(
        "pydecimal", left_digits=2, right_digits=3, positive=True, max_value=5
    )

    # Viscosity (cSt)
    viscosity_40c = factory.Faker(
        "pydecimal",
        left_digits=3,
        right_digits=2,
        positive=True,
        min_value=20,
        max_value=500,
    )
    viscosity_100c = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=True,
        min_value=5,
        max_value=50,
    )

    # Acid/Base Numbers (mgKOH/g)
    compatibility = factory.Faker(
        "random_element", elements=["COMPATIBLE", "INCOMPATIBLE", ""]
    )
    tbn = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=True,
        min_value=1,
        max_value=15,
    )
    tan = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=True,
        min_value=0.5,
        max_value=5,
    )

    # FTIR Analysis
    oxidation = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=3,
        positive=True,
        max_value=50,
    )
    soot = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=3,
        positive=True,
        max_value=5,
    )
    nitration = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=3,
        positive=True,
        max_value=30,
    )
    sulfation = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=3,
        positive=True,
        max_value=30,
    )
    glycol = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=3,
        positive=True,
        max_value=5,
    )
    fuel_dilution = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=3,
        positive=True,
        max_value=10,
    )
    water_ftir = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=3,
        positive=True,
        max_value=5,
    )

    # Particle Analysis
    pq_index = factory.Faker("random_int", min=0, max=200)
    particle_count_iso = factory.Faker(
        "random_element", elements=["20/18/15", "19/17/14", "21/19/16", ""]
    )

    # Wear Metals (ppm)
    iron_fe = factory.Faker("random_int", min=0, max=200)
    chromium_cr = factory.Faker("random_int", min=0, max=50)
    lead_pb = factory.Faker("random_int", min=0, max=100)
    copper_cu = factory.Faker("random_int", min=0, max=150)
    tin_sn = factory.Faker("random_int", min=0, max=50)
    aluminum_al = factory.Faker("random_int", min=0, max=80)
    nickel_ni = factory.Faker("random_int", min=0, max=30)
    silver_ag = factory.Faker("random_int", min=0, max=20)

    # Contaminants (ppm)
    silicon_si = factory.Faker("random_int", min=0, max=150)
    boron_b = factory.Faker("random_int", min=0, max=50)
    sodium_na = factory.Faker("random_int", min=0, max=250)
    magnesium_mg = factory.Faker("random_int", min=0, max=100)
    potassium_k = factory.Faker("random_int", min=0, max=50)

    # Additives (ppm)
    molybdenum_mo = factory.Faker("random_int", min=0, max=200)
    titanium_ti = factory.Faker("random_int", min=0, max=20)
    vanadium_v = factory.Faker("random_int", min=0, max=20)
    manganese_mn = factory.Faker("random_int", min=0, max=20)
    phosphorus_p = factory.Faker("random_int", min=0, max=1500)
    zinc_zn = factory.Faker("random_int", min=0, max=1500)
    calcium_ca = factory.Faker("random_int", min=0, max=3000)
    barium_ba = factory.Faker("random_int", min=0, max=50)
    cadmium_cd = factory.Faker("random_int", min=0, max=10)

    # Qualitative contamination tests
    dispersancy = factory.Sequence(
        lambda n: DISPERSANCY_RATINGS[n % len(DISPERSANCY_RATINGS)]
    )
    spot_test = factory.Sequence(lambda n: SPOT_TESTS[n % len(SPOT_TESTS)])

    # Visual
    visual_appearance = factory.Sequence(
        lambda n: VISUAL_APPEARANCES[n % len(VISUAL_APPEARANCES)]
    )


class NormalConditionLabAnalysisFactory(LabAnalysisFactory):
    """Factory for creating LabAnalysis with normal condition values."""

    # Wear metals - normal range
    iron_fe = factory.Faker("random_int", min=0, max=40)
    copper_cu = factory.Faker("random_int", min=0, max=25)
    aluminum_al = factory.Faker("random_int", min=0, max=15)

    # Contaminants - normal range
    silicon_si = factory.Faker("random_int", min=0, max=25)
    sodium_na = factory.Faker("random_int", min=0, max=40)
    fuel_dilution = factory.Faker(
        "pydecimal", left_digits=1, right_digits=2, positive=True, max_value=2.5
    )

    # Oil health - good condition
    tbn = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=True,
        min_value=5,
        max_value=12,
    )
    tan = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        max_value=2,
    )
    oxidation = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=True,
        max_value=15,
    )


class CautionConditionLabAnalysisFactory(LabAnalysisFactory):
    """Factory for creating LabAnalysis with caution condition values."""

    # Wear metals - caution range
    iron_fe = factory.Faker("random_int", min=50, max=100)
    copper_cu = factory.Faker("random_int", min=30, max=50)
    aluminum_al = factory.Faker("random_int", min=20, max=40)

    # Contaminants - caution range
    silicon_si = factory.Faker("random_int", min=30, max=50)
    sodium_na = factory.Faker("random_int", min=50, max=100)
    fuel_dilution = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        min_value=3,
        max_value=5,
    )

    # Oil health - degraded condition
    tbn = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        min_value=2,
        max_value=5,
    )
    tan = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        min_value=2,
        max_value=4,
    )
    oxidation = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=True,
        min_value=20,
        max_value=30,
    )


class CriticalConditionLabAnalysisFactory(LabAnalysisFactory):
    """Factory for creating LabAnalysis with critical condition values."""

    # Wear metals - critical range
    iron_fe = factory.Faker("random_int", min=100, max=200)
    copper_cu = factory.Faker("random_int", min=50, max=150)
    aluminum_al = factory.Faker("random_int", min=40, max=80)

    # Contaminants - critical range
    silicon_si = factory.Faker("random_int", min=50, max=150)
    sodium_na = factory.Faker("random_int", min=100, max=250)
    fuel_dilution = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        min_value=5,
        max_value=10,
    )

    # Oil health - severely degraded condition
    tbn = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        max_value=2,
    )
    tan = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=2,
        positive=True,
        min_value=4,
        max_value=8,
    )
    oxidation = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=True,
        min_value=30,
        max_value=50,
    )


class AnalysisThresholdFactory(factory.django.DjangoModelFactory):
    """Factory for creating AnalysisThreshold test instances."""

    class Meta:
        model = models.AnalysisThreshold

    component_type = None  # Can be overridden to create type-specific thresholds
    category = factory.Iterator(choices.Category.values)
    parameter = factory.Iterator(choices.Parameter.values)
    warning_limit = factory.Faker("random_int", min=50, max=100)
    critical_limit = factory.Faker("random_int", min=100, max=200)
    unit = "ppm"
    is_inverse = False
    wear_source_description = factory.Sequence(
        lambda n: WEAR_SOURCES[n % len(WEAR_SOURCES)]
    )
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")
