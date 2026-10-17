from django.db import models
from django.utils.translation import gettext_lazy as _


class OrganizationKind(models.TextChoices):
    """Kind of organization within the tenancy tree."""

    PLATFORM = "platform", _("Platform")
    LAB = "lab", _("Laboratory")
    INTERMEDIARY = "intermediary", _("Intermediary")
    FINAL = "final", _("Final client")
