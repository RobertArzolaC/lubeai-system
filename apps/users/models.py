from typing import ClassVar

from allauth.account.models import EmailAddress
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from model_utils.models import SoftDeletableModel, TimeStampedModel

from apps.core import models as core_models
from apps.users.managers import CustomUserManager


class User(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), unique=True)
    avatar = models.ImageField(upload_to="users/avatars/", null=True, blank=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name=_("Organization"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text=_("Tenant/client organization this user belongs to"),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    @cached_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @cached_property
    def is_account(self):
        return hasattr(self, "account")

    @cached_property
    def is_email_verified(self):
        """Return ``True`` when the user has a verified email address."""
        return EmailAddress.objects.filter(user=self, verified=True).exists()

    @cached_property
    def tenant(self):
        """Return the root tenant of this user's organization, if any."""
        return self.organization.tenant if self.organization_id else None


class Account(SoftDeletableModel, TimeStampedModel):
    user = models.OneToOneField(
        User,
        verbose_name=_("User"),
        on_delete=models.CASCADE,
        related_name="account",
    )

    class Meta:
        verbose_name = _("Account")
        verbose_name_plural = _("Accounts")
        ordering = ("user__last_name", "user__first_name")

    def __str__(self):
        return self.user.get_full_name()

    @cached_property
    def full_name(self):
        return self.user.get_full_name()

    @cached_property
    def is_email_verified(self):
        return EmailAddress.objects.filter(user=self.user, verified=True).exists()


class Role(TimeStampedModel, core_models.BaseUserTracked, core_models.IsActive):
    """A tenant-scoped role backed by a Django :class:`~django.contrib.auth.models.Group`.

    Each role belongs to an organization and wraps a single ``auth.Group`` whose
    permissions define what the role can do. Assigning a role to a user adds the
    backing group to the user's groups, so Django's permission model keeps
    working unchanged.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name=_("Organization"),
        on_delete=models.CASCADE,
        related_name="roles",
        help_text=_("Organization this role belongs to"),
    )
    name = models.CharField(_("Name"), max_length=120)
    slug = models.SlugField(
        _("Slug"),
        max_length=140,
        help_text=_("Stable identifier, unique within the organization"),
    )
    description = models.TextField(_("Description"), blank=True)
    group = models.OneToOneField(
        "auth.Group",
        verbose_name=_("Django group"),
        on_delete=models.CASCADE,
        related_name="role",
        help_text=_("Group that stores this role's permissions"),
    )

    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ("name",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                name="users_role_unique_org_slug",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organization"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        """Return ``"<name> (<organization>)"``."""
        return f"{self.name} ({self.organization.name})"
