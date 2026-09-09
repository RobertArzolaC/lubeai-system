import factory
from django.contrib.auth import get_user_model

from apps.users import models

User = get_user_model()


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


class AccountFactory(factory.django.DjangoModelFactory):
    """Factory that reuses the ``Account`` auto-created by the user signal."""

    class Meta:
        model = models.Account

    user = factory.SubFactory(UserFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        user = kwargs.pop("user")
        account, _created = model_class.objects.get_or_create(
            user=user, defaults=kwargs
        )
        return account
