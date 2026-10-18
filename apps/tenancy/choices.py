"""Choices for the shared tenancy registry."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class TenantKind(models.TextChoices):
    """Kind of platform client a tenant represents.

    Mirrors :class:`apps.organizations.choices.OrganizationKind` on purpose
    instead of importing it: this app lives in ``SHARED_APPS`` and must not
    depend on an app that lives in ``TENANT_APPS``. Keeping the string values
    identical lets both trees be compared without a mapping table.
    """

    PLATFORM = "platform", _("Platform")
    LAB = "lab", _("Laboratory")
    INTERMEDIARY = "intermediary", _("Intermediary")
    FINAL = "final", _("Final client")
