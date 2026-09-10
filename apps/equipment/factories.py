import factory

from apps.equipment import choices, models
from apps.users import factories as user_factories

PORTS = [
    "Puerto de Valparaíso",
    "Puerto del Callao",
    "Puerto de Cartagena",
    "Puerto de Veracruz",
    "Puerto de Buenos Aires",
    "Puerto de Santander",
    "Puerto de Tampico",
    "Puerto de Guayaquil",
]

FLEETS = [
    "Flota Pacífico Sur",
    "Flota Atlántica",
    "Flota del Caribe",
    "Flota Mediterránea",
    "Flota de Remolcadores",
    "Flota Pesquera Industrial",
    "Flota Naval Auxiliar",
    "Flota de Cabotaje",
]

VESSELS = [
    "Motonave Pacífico",
    "Buque Tanque Andino",
    "Remolcador Titán",
    "Barcaza Marina",
    "Portacontenedores Alerce",
    "Buque Pesquero Albatros",
    "Fragata Covadonga",
    "Ferry Estrecho de Magallanes",
    "Petrolero Golfo Nuevo",
    "Carguero Austral",
]

VESSEL_MODELS = [
    "MAN B&W 6S50MC",
    "Wärtsilä 8L20",
    "Caterpillar 3512C",
    "Cummins KTA19",
    "MAN B&W 7S60ME",
    "Caterpillar 3412E",
    "MTU 20V1163",
    "Wärtsilä 12V46",
    "MAK 6M32C",
    "Sulzer 6RTA48",
]

COMPONENT_TYPES = [
    "Motor Principal",
    "Motor Generador Auxiliar",
    "Caja Reductora",
    "Bomba de Lastre",
    "Separador de Combustible",
    "Turbina de Vapor",
    "Sistema Hidráulico de Cubierta",
    "Hélice de Paso Variable",
    "Enfriador de Aceite",
    "Purificador de Combustible",
]

BRANCH_DESCRIPTIONS = [
    "Base portuaria para operaciones de carga y descarga.",
    "Terminal marítimo con servicios de atraque y suministro.",
    "Muelle de cabotaje y reparaciones a flote.",
    "Estación naval de mantenimiento y avituallamiento.",
    "Puerto base para la flota de altura.",
    "Terminal de graneles y embarque marítimo.",
]

COMPONENT_TYPE_DESCRIPTIONS = [
    "Componente crítico del sistema de propulsión.",
    "Equipo auxiliar del sistema de generación eléctrica.",
    "Elemento de transmisión y reducción de velocidad.",
    "Sistema de bombeo y lastre del buque.",
    "Equipo de tratamiento y purificación de combustible.",
    "Componente del sistema hidráulico de cubierta.",
]


class FleetFactory(factory.django.DjangoModelFactory):
    """Factory for maritime fleet test instances."""

    class Meta:
        model = models.Fleet

    name = factory.Sequence(lambda n: FLEETS[n % len(FLEETS)])
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class BranchFactory(factory.django.DjangoModelFactory):
    """Factory for maritime port/branch test instances."""

    class Meta:
        model = models.Branch

    name = factory.Sequence(lambda n: PORTS[n % len(PORTS)])
    description = factory.Sequence(
        lambda n: BRANCH_DESCRIPTIONS[n % len(BRANCH_DESCRIPTIONS)]
    )
    address = factory.Sequence(lambda n: f"Terminal Marítimo {n + 1}, Zona Portuaria")
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class MachineFactory(factory.django.DjangoModelFactory):
    """Factory for maritime vessel test instances."""

    class Meta:
        model = models.Machine

    branch = factory.SubFactory(BranchFactory)
    fleet = factory.SubFactory(FleetFactory)
    name = factory.Sequence(lambda n: VESSELS[n % len(VESSELS)])
    serial_number = factory.Sequence(lambda n: f"IMO {9000000 + n}")
    model = factory.Sequence(lambda n: VESSEL_MODELS[n % len(VESSEL_MODELS)])
    measurement_unit = choices.MeasurementUnit.HOURS
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class ComponentTypeFactory(factory.django.DjangoModelFactory):
    """Factory for maritime component type test instances."""

    class Meta:
        model = models.ComponentType

    name = factory.Sequence(lambda n: COMPONENT_TYPES[n % len(COMPONENT_TYPES)])
    description = factory.Sequence(
        lambda n: COMPONENT_TYPE_DESCRIPTIONS[n % len(COMPONENT_TYPE_DESCRIPTIONS)]
    )
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class ComponentFactory(factory.django.DjangoModelFactory):
    """Factory for maritime component test instances."""

    class Meta:
        model = models.Component

    machine = factory.SubFactory(MachineFactory)
    type = factory.SubFactory(ComponentTypeFactory)
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")
