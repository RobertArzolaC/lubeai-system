import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.users import models

User = get_user_model()


class GroupFactory(factory.django.DjangoModelFactory):
    """Factory for the Django ``auth.Group`` used to back a role."""

    class Meta:
        model = Group

    name = factory.Sequence(lambda n: f"group-{n}")


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for the custom :class:`User` model (email is the username)."""

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(self, create: bool, extracted: str | None, **kwargs: object) -> None:
        """Set a usable (hashed) password on the created user."""
        password = extracted or "Passw0rd!123"
        self.set_password(password)
        if create:
            self.save(update_fields=["password"])


class RoleFactory(factory.django.DjangoModelFactory):
    """Factory for the tenant-scoped :class:`models.Role` model."""

    class Meta:
        model = models.Role

    organization = factory.SubFactory(
        "apps.organizations.factories.OrganizationFactory"
    )
    name = factory.Sequence(lambda n: f"Role {n}")
    slug = factory.Sequence(lambda n: f"role-{n}")
    description = ""
    is_active = True
    group = factory.SubFactory(GroupFactory)
    created_by = factory.SubFactory(UserFactory)
    updated_by = factory.SelfAttribute("created_by")
