"""Create the MARCO tenant and attach the existing data to it."""

from __future__ import annotations

from django.db import migrations

MARCO_SLUG = "marco"

# (app_label, model_name) of the models that belong to an organization.
TENANT_MODELS: list[tuple[str, str]] = [
    ("equipment", "Branch"),
    ("equipment", "Fleet"),
    ("equipment", "Machine"),
    ("reports", "Report"),
    ("alerts", "Alert"),
]


def create_marco_tenant(apps, schema_editor) -> None:
    """Create the MARCO root tenant and backfill the existing data."""
    organization = apps.get_model("organizations", "Organization")
    marco, _ = organization.objects.get_or_create(
        slug=MARCO_SLUG,
        defaults={
            "name": "MARCO Peruana",
            "kind": "lab",
            "is_active": True,
        },
    )

    for app_label, model_name in TENANT_MODELS:
        model = apps.get_model(app_label, model_name)
        model.objects.filter(organization__isnull=True).update(organization=marco)

    user = apps.get_model("users", "User")
    user.objects.filter(organization__isnull=True).update(organization=marco)


def remove_marco_tenant(apps, schema_editor) -> None:
    """Detach the data from MARCO and delete the tenant (reverse)."""
    organization = apps.get_model("organizations", "Organization")
    marco = organization.objects.filter(slug=MARCO_SLUG).first()
    if marco is None:
        return

    for app_label, model_name in TENANT_MODELS:
        model = apps.get_model(app_label, model_name)
        model.objects.filter(organization=marco).update(organization=None)

    user = apps.get_model("users", "User")
    user.objects.filter(organization=marco).update(organization=None)

    # Never cascade-delete a populated subtree on rollback.
    if marco.children.exists():
        return
    marco.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("users", "0003_user_organization"),
        ("equipment", "0002_branch_organization_fleet_organization_and_more"),
        ("reports", "0003_report_organization"),
        ("alerts", "0004_alert_organization"),
    ]

    operations = [
        migrations.RunPython(create_marco_tenant, remove_marco_tenant),
    ]
