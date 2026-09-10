from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel

from apps.core import models as core_models
from apps.equipment import choices


class Fleet(TimeStampedModel, core_models.BaseUserTracked, core_models.IsActive):
    name = models.CharField(_("Name"), max_length=200, help_text=_("Fleet name"))

    class Meta:
        verbose_name = _("Fleet")
        verbose_name_plural = _("Fleets")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return string representation of the fleet."""
        return self.name


class Branch(
    TimeStampedModel,
    core_models.BaseAddress,
    core_models.BaseUserTracked,
    core_models.NameDescription,
    core_models.IsActive,
):
    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return string representation of branch."""
        return self.name


class Machine(TimeStampedModel, core_models.BaseUserTracked, core_models.IsActive):
    """
    Machine model.

    Represents industrial equipment/machinery used for condition monitoring
    and predictive maintenance.
    """

    branch = models.ForeignKey(
        Branch,
        verbose_name=_("Branch"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="machines",
        help_text=_("Branch/location where this machine is placed"),
    )
    fleet = models.ForeignKey(
        Fleet,
        verbose_name=_("Fleet"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="machines",
        help_text=_("Optional fleet grouping for this machine"),
    )
    name = models.CharField(
        _("Name"),
        max_length=200,
        help_text=_("Machine name or identifier"),
    )
    serial_number = models.CharField(
        _("Serial Number"),
        max_length=100,
        help_text=_("Unique serial number of the machine"),
    )
    model = models.CharField(
        _("Model"),
        max_length=200,
        help_text=_("Machine model or type designation"),
    )
    measurement_unit = models.CharField(
        _("Measurement Unit"),
        max_length=10,
        choices=choices.MeasurementUnit.choices,
        default=choices.MeasurementUnit.KILOMETERS,
        help_text=_("Unit of measurement for machine usage"),
    )

    class Meta:
        verbose_name = _("Machine")
        verbose_name_plural = _("Machines")
        ordering = ("name",)
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["name"]),
            models.Index(fields=["serial_number"]),
        ]

    def __str__(self) -> str:
        """Return string representation of machine."""
        if self.serial_number:
            return f"{self.name} ({self.serial_number})"
        return self.name


class ComponentType(
    TimeStampedModel,
    core_models.BaseUserTracked,
    core_models.NameDescription,
    core_models.IsActive,
):
    """
    Component Type model.

    Represents categories/types of industrial components
    (e.g., Pump, Motor, Compressor, Turbine, etc.)
    """

    class Meta:
        verbose_name = _("Component Type")
        verbose_name_plural = _("Component Types")
        ordering = ("name",)


class Component(TimeStampedModel, core_models.BaseUserTracked, core_models.IsActive):
    """
    Component model.

    Represents parts or components installed in a machine.
    """

    machine = models.ForeignKey(
        Machine,
        verbose_name=_("Machine"),
        on_delete=models.CASCADE,
        related_name="components",
        help_text=_("Machine this component belongs to"),
    )
    type = models.ForeignKey(
        ComponentType,
        verbose_name=_("Type"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="components",
        help_text=_("Type/category of this component"),
    )

    class Meta:
        verbose_name = _("Component")
        verbose_name_plural = _("Components")
        ordering = ("machine", "type")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["machine", "is_active"]),
        ]

    def __str__(self) -> str:
        """Return string representation of component."""
        type_name = self.type.name if self.type else "Unknown Type"
        return f"{type_name}({self.machine.name})"
