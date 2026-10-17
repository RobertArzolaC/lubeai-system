import factory

from apps.organizations import choices, models
from apps.users import factories as user_factories


class OrganizationFactory(factory.django.DjangoModelFactory):
    """Factory for the Organization tenancy model."""

    class Meta:
        model = models.Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.Sequence(lambda n: f"organization-{n}")
    code = factory.Sequence(lambda n: f"ORG-{n:05d}")
    kind = choices.OrganizationKind.FINAL
    parent = None
    is_active = True
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")
