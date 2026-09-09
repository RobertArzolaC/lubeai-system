from typing import ClassVar

from cities_light.models import City, Country, Region, SubRegion
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel

from apps.core import choices


class BaseAddress(models.Model):
    address = models.CharField(_("Address"), max_length=255, blank=True)
    zip_code = models.CharField(_("Zip code"), max_length=255, blank=True)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    subregion = models.ForeignKey(
        SubRegion, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        abstract = True


class BaseContact(models.Model):
    phone = models.CharField(_("Phone"), max_length=20, blank=True)
    email = models.EmailField(_("Email"), blank=True)

    class Meta:
        abstract = True


class BaseUserTracked(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class Person(BaseAddress, BaseContact):
    first_name = models.CharField(_("First name"), max_length=150)
    paternal_last_name = models.CharField(_("Paternal last name"), max_length=150)
    maternal_last_name = models.CharField(_("Maternal last name"), max_length=150)
    document_type = models.CharField(
        _("Document type"),
        max_length=20,
        choices=choices.DocumentType.choices,
        default=choices.DocumentType.DOCUMENT,
    )
    document_number = models.CharField(_("Document number"), max_length=20, unique=True)
    gender = models.CharField(
        _("Gender"),
        max_length=1,
        choices=choices.Gender.choices,
        default=choices.Gender.MALE,
    )
    birth_date = models.DateField(_("Birth date"), null=True, blank=True)
    user = models.OneToOneField(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s",
        verbose_name=_("User"),
        help_text=_("User account associated with this person"),
    )

    class Meta:
        abstract = True

    def __str__(self):
        base_str = (
            f"{self.first_name} {self.paternal_last_name} ({self.document_number})"
        )
        if self.maternal_last_name:
            base_str = f"{self.first_name} {self.paternal_last_name} {self.maternal_last_name} ({self.document_number})"
        return base_str

    @property
    def full_name(self):
        if self.maternal_last_name:
            return (
                f"{self.first_name} {self.paternal_last_name} {self.maternal_last_name}"
            )
        return f"{self.first_name} {self.paternal_last_name}"

    @property
    def short_name(self):
        return f"{self.first_name} {self.paternal_last_name}"

    @property
    def initials(self):
        initials = self.first_name[0] if self.first_name else ""
        initials += self.paternal_last_name[0] if self.paternal_last_name else ""
        return initials.upper()

    @property
    def age(self):
        if hasattr(self, "birth_date") and self.birth_date:
            today = timezone.localdate()
            age = today.year - self.birth_date.year
            if (today.month, today.day) < (
                self.birth_date.month,
                self.birth_date.day,
            ):
                age -= 1
            return age
        return None


class NameDescription(models.Model):
    name = models.CharField(_("Name"), max_length=200)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class IsActive(models.Model):
    is_active = models.BooleanField(
        _("Is active"),
        default=True,
        help_text=_("Designates whether this entry is active"),
    )

    class Meta:
        abstract = True


class StatusHistory(BaseUserTracked, TimeStampedModel):
    """Generic abstract model to track status changes for any model."""

    status = models.CharField(
        _("Status"),
        max_length=50,
        help_text=_("New status value."),
    )
    previous_status = models.CharField(
        _("Previous Status"),
        max_length=50,
        blank=True,
        help_text=_("Previous status value."),
    )
    note = models.TextField(
        _("Note"),
        blank=True,
        help_text=_("Optional note about the status change."),
    )

    class Meta:
        abstract = True
        verbose_name = _("Status History")
        verbose_name_plural = _("Status Histories")
        ordering: ClassVar[list[str]] = ["-created"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["created"]),
        ]

    def __str__(self) -> str:
        return f"{self.previous_status} → {self.status}"

    @property
    def changed_by(self):
        """Alias for updated_by to maintain API compatibility."""
        return self.updated_by

    @property
    def changed_at(self):
        """Alias for created to maintain API compatibility."""
        return self.created

    def get_parent_filters(self) -> dict:
        """
        Return a dictionary with the filters needed to uniquely identify the parent object.
        Example: return {"order": self.order}
        """
        raise NotImplementedError("Subclasses must implement get_parent_filters()")

    @classmethod
    def get_parent_kwargs(cls, instance) -> dict:
        """
        Return the kwargs to set the parent ForeignKey on creation.
        Example: return {"order": instance}
        """
        raise NotImplementedError("Subclasses must implement get_parent_kwargs()")

    @property
    def duration_in_status(self):
        """Calculate duration this status was active."""
        next_change = self.__class__.objects.filter(
            **self.get_parent_filters(),
            created__gt=self.created,
        ).first()

        end_time = next_change.created if next_change else timezone.now()
        return end_time - self.created

    def get_duration_in_days(self) -> int:
        """Get duration in days."""
        return self.duration_in_status.days

    def get_duration_in_hours(self) -> int:
        """Get duration in hours."""
        return int(self.duration_in_status.total_seconds() / 3600)

    @classmethod
    def create_status_change(
        cls,
        instance,
        new_status: str,
        user,
        note: str = "",
        previous_status: str | None = None,
    ):
        """Create a status history entry for an instance."""
        if not previous_status:
            previous_status = getattr(instance, "status", "")

        return cls.objects.create(
            status=new_status,
            previous_status=previous_status,
            note=note,
            created_by=user,
            updated_by=user,
            **cls.get_parent_kwargs(instance),
        )
