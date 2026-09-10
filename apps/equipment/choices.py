from django.db import models
from django.utils.translation import gettext_lazy as _


class MeasurementUnit(models.TextChoices):
    KILOMETERS = "KM", _("Kilómetros")
    HOURS = "HOURS", _("Horas")
    BOTH = "BOTH", _("Ambos")
