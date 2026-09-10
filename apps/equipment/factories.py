import factory

from apps.equipment import models
from apps.users import factories as user_factories


class FleetFactory(factory.django.DjangoModelFactory):
    """Factory for creating Fleet test instances."""

    class Meta:
        model = models.Fleet

    name = factory.Sequence(lambda n: f"Fleet {n}")
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class BranchFactory(factory.django.DjangoModelFactory):
    """Factory for Branch model."""

    class Meta:
        model = models.Branch

    name = factory.Sequence(lambda n: f"Branch {n}")
    description = factory.Faker("text", max_nb_chars=200)
    address = factory.Faker("street_address")
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class MachineFactory(factory.django.DjangoModelFactory):
    """Factory for Machine model."""

    class Meta:
        model = models.Machine

    branch = factory.SubFactory(BranchFactory)
    fleet = factory.SubFactory(FleetFactory)
    name = factory.Faker("word")
    serial_number = factory.Sequence(lambda n: f"SN-{n:06d}")
    model = factory.Faker("word")
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class ComponentTypeFactory(factory.django.DjangoModelFactory):
    """Factory for ComponentType model."""

    class Meta:
        model = models.ComponentType

    name = factory.Sequence(lambda n: f"Component Type {n}")
    description = factory.Faker("text", max_nb_chars=200)
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")


class ComponentFactory(factory.django.DjangoModelFactory):
    """Factory for Component model."""

    class Meta:
        model = models.Component

    machine = factory.SubFactory(MachineFactory)
    type = factory.SubFactory(ComponentTypeFactory)
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")
