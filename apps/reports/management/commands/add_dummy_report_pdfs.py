"""Run the dummy PDF backfill once per tenant schema.

``reports`` is a TENANT app, so the command can only run with a schema
selected: this wrapper runs :mod:`add_dummy_report_pdfs_tenant` against every
tenant, or against the one given with ``--schema``.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import CommandParser
from django_tenants.management.commands import BaseTenantCommand


class Command(BaseTenantCommand):
    """Attach a dummy PDF to reports without one in every tenant."""

    COMMAND_NAME = "add_dummy_report_pdfs_tenant"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add the wrapper flags and the options the wrapped command accepts.

        Args:
            parser: The command's argument parser.
        """
        super().add_arguments(parser)
        parser.set_defaults(skip_public=True)
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing PDFs as well. This deletes the current files.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process at most this many reports per tenant.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many reports would be updated.",
        )

    def execute_command(
        self, tenant: Any, command_name: str, *args: Any, **options: Any
    ) -> None:
        """Run the wrapped command without the wrapper-only options.

        Args:
            tenant: Tenant whose schema the wrapped command runs against.
            command_name: Name of the wrapped command.
            *args: Positional arguments for the wrapped command.
            **options: Options parsed by this wrapper.
        """
        options.pop("schema_name", None)
        options.pop("skip_public", None)
        super().execute_command(tenant, command_name, *args, **options)
