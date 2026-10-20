"""Clear expired OAuth codes and tokens in every tenant schema."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection
from django_mcpz.oauth.cleanup import clear_expired

from apps.tenancy import models as tenancy_models


class Command(BaseCommand):
    """Run the django-mcpz OAuth cleanup once per tenant schema."""

    help = (
        "Delete expired and revoked OAuth codes/tokens in every tenant schema. "
        "Schedule it daily (for example with cron or a systemd timer)."
    )

    def handle(self, *args, **options) -> None:
        """Iterate the tenant registry and clean each schema."""
        tenants = list(
            tenancy_models.Tenant.objects.exclude(schema_name="public").order_by(
                "schema_name"
            )
        )
        previous_tenant = connection.tenant
        totals = {
            "refresh_tokens": 0,
            "access_tokens": 0,
            "codes": 0,
            "clients": 0,
        }
        try:
            for tenant in tenants:
                connection.set_tenant(tenant)
                result = clear_expired()
                for key, value in result.items():
                    totals[key] += value
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{tenant.schema_name}: "
                        + ", ".join(f"{key}={value}" for key, value in result.items())
                    )
                )
        finally:
            if previous_tenant is not None:
                connection.set_tenant(previous_tenant)
            else:
                connection.set_schema_to_public()

        self.stdout.write(
            self.style.SUCCESS(
                "Total: " + ", ".join(f"{key}={value}" for key, value in totals.items())
            )
        )
