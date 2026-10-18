"""Management command that provisions a tenant.

Usage::

    manage.py provision_tenant --slug acme --name "ACME" --kind intermediary \\
        --admin-email admin@acme.pe

The command is a thin wrapper around :func:`apps.tenancy.services.provision_tenant`
so the same behaviour is available from code (the platform's own tenant
administration) and from a shell.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.tenancy import choices, constants, services


class Command(BaseCommand):
    """Provision a tenant and leave it operative."""

    help = (
        "Create a tenant with its schema, domain, Site, root organization, "
        "admin user and default component types."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command options.

        Args:
            parser: The command's argument parser.
        """
        parser.add_argument("--slug", required=True, help="Tenant slug/schema name.")
        parser.add_argument("--name", required=True, help="Human-readable name.")
        parser.add_argument(
            "--kind",
            required=True,
            choices=choices.TenantKind.values,
            help="Kind of platform client.",
        )
        parser.add_argument(
            "--admin-email", required=True, help="Email of the tenant admin."
        )
        parser.add_argument(
            "--default-password",
            default=constants.DEMO_PASSWORD,
            help="Password for the admin when it is created.",
        )
        parser.add_argument(
            "--domain",
            default=None,
            help="Host name (defaults to <slug>.<PLATFORM_DOMAIN>).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Provision the tenant described by the options.

        Args:
            *args: Unused positional arguments.
            **options: Parsed management options.

        Raises:
            CommandError: If the tenant kind is invalid, the slug is the public
                schema or the domain already belongs to another tenant.
        """
        try:
            tenant = services.provision_tenant(
                slug=options["slug"],
                name=options["name"],
                kind=options["kind"],
                admin_email=options["admin_email"],
                default_password=options["default_password"],
                domain=options["domain"],
            )
        except ValueError as error:
            raise CommandError(str(error)) from error

        domain = tenant.get_primary_domain()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant '{tenant.name}' provisioned.\n"
                f"- Schema: {tenant.schema_name}\n"
                f"- Domain: {domain.domain if domain else '-'}\n"
                f"- Admin: {options['admin_email']}"
            )
        )
