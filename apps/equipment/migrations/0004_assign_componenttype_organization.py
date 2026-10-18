"""Assign the existing component types to the MARCO tenant."""

from __future__ import annotations

from django.db import migrations

MARCO_SLUG = "marco"


def assign_to_marco(apps, schema_editor) -> None:
    """Attach every organization-less component type to the MARCO tenant."""
    organization = apps.get_model("organizations", "Organization")
    marco = organization.objects.filter(slug=MARCO_SLUG).first()
    if marco is None:
        return

    component_type = apps.get_model("equipment", "ComponentType")
    component_type.objects.filter(organization__isnull=True).update(organization=marco)


def unassign_from_marco(apps, schema_editor) -> None:
    """Detach the component types owned by MARCO (reverse)."""
    organization = apps.get_model("organizations", "Organization")
    marco = organization.objects.filter(slug=MARCO_SLUG).first()
    if marco is None:
        return

    component_type = apps.get_model("equipment", "ComponentType")
    component_type.objects.filter(organization=marco).update(organization=None)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("equipment", "0003_componenttype_organization_and_more"),
    ]

    operations = [
        migrations.RunPython(assign_to_marco, unassign_from_marco),
    ]
