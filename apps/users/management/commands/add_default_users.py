"""Public entry point for the default-user seeding command.

``users`` is a TENANT app, so its command can only run with a schema selected:
this wrapper runs :mod:`apps.users.management.commands.add_default_users_tenant`
against every tenant, or against the one given with ``--schema``.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import CommandParser
from django_tenants.management.commands import BaseTenantCommand


class Command(BaseTenantCommand):
    """Run the default-user seeding once per tenant schema."""

    COMMAND_NAME = "add_default_users_tenant"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add the wrapper flags and the password the wrapped command accepts.

        The wrapped command is not imported by ``BaseTenantCommand`` when the
        parser is built, so the password option is declared here and forwarded
        through :meth:`execute_command`.

        Args:
            parser: The command's argument parser.
        """
        super().add_arguments(parser)
        parser.add_argument(
            "--password",
            default=None,
            help=(
                "Password for the created users, validated with Django's "
                "configured validators. A random one is generated and printed "
                "once when omitted."
            ),
        )

    def execute_command(
        self, tenant: Any, command_name: str, *args: Any, **options: Any
    ) -> None:
        """Run the wrapped command with only the options it declares.

        ``BaseTenantCommand`` forwards its own ``--schema`` / ``--skip-public``
        flags to the wrapped command, which does not declare them: ``call_command``
        would reject them with a ``TypeError``.

        Args:
            tenant: Tenant whose schema the wrapped command runs against.
            command_name: Name of the wrapped command.
            *args: Positional arguments for the wrapped command.
            **options: Options parsed by this wrapper.
        """
        options.pop("schema_name", None)
        options.pop("skip_public", None)
        super().execute_command(tenant, command_name, *args, **options)
