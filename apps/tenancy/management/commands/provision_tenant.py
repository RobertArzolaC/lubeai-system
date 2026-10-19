"""Management command that provisions a tenant.

Usage::

    manage.py provision_tenant --slug acme --name "ACME" --kind intermediary \\
        --admin-email admin@acme.pe

The command is a thin wrapper around :func:`apps.tenancy.services.provision_tenant`
so the same behaviour is available from code (the platform's own tenant
administration) and from a shell.

The administrator password follows the same criterion as the tenant console: it
is validated with Django's configured validators and there is no repository
default to fall back on. When ``--default-password`` is omitted a random one is
generated and printed **once**; because the service only applies a password to a
newly created administrator, the command prints it only when it is actually
applied.
"""

from __future__ import annotations

import secrets
import string
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DatabaseError
from django_tenants.utils import (
    get_public_schema_name,
    schema_exists,
    tenant_context,
)

from apps.tenancy import choices, models, services

#: Alphabet used for generated passwords. Avoids characters that are easy to
#: confuse when read from a terminal (``l``/``1``, ``O``/``0``).
PASSWORD_ALPHABET: str = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
PASSWORD_LENGTH: int = 16


def generate_password(length: int = PASSWORD_LENGTH) -> str:
    """Return a random administrator password.

    Args:
        length: Number of characters to draw from :data:`PASSWORD_ALPHABET`.

    Returns:
        A cryptographically random password, long enough to pass Django's
        default length validator.
    """
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


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
            default=None,
            help=(
                "Password for the administrator. A random one is generated and "
                "printed once when omitted. Either way it is only applied when "
                "the administrator is created."
            ),
        )
        parser.add_argument(
            "--domain",
            default=None,
            help=(
                "Host name served by the tenant. Defaults to "
                "<slug>.<TENANT_HOST_SUFFIX>; required when that suffix is empty."
            ),
        )
        parser.add_argument(
            "--promote",
            action="store_true",
            default=False,
            help=(
                "Elevate an account that already uses --admin-email to "
                "administrator. Off by default so re-running the command never "
                "escalates a normal client user."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Provision the tenant described by the options.

        Args:
            *args: Unused positional arguments.
            **options: Parsed management options.

        Raises:
            CommandError: If the tenant kind is invalid, the slug is the public
                schema, the domain already belongs to another tenant or the
                password does not pass Django's validators.
        """
        password = self._resolve_password(options["default_password"])
        admin_existed = self._admin_exists(
            slug=options["slug"], email=options["admin_email"]
        )

        try:
            tenant = services.provision_tenant(
                slug=options["slug"],
                name=options["name"],
                kind=options["kind"],
                admin_email=options["admin_email"],
                default_password=password,
                domain=options["domain"],
                promote=options["promote"],
            )
        except ValueError as error:
            raise CommandError(str(error)) from error

        applied_password = None if admin_existed else password
        self.stdout.write(
            self.style.SUCCESS(self._summary(tenant, options, applied_password))
        )
        if admin_existed:
            self.stdout.write(
                "The administrator already existed, so its password was not changed."
            )
        else:
            self.stdout.write(
                "Store the password now: it is only shown once and is not "
                "recoverable from the platform."
            )

    @staticmethod
    def _resolve_password(provided: str | None) -> str:
        """Return a validated administrator password.

        There is no repository default: a publicly known password must never be
        able to stand up a production client, which is why the tenant console
        requires one too.

        Args:
            provided: Password from ``--default-password``, if any.

        Returns:
            ``provided`` when given, otherwise a freshly generated password.

        Raises:
            CommandError: If the password fails Django's configured validators.
        """
        password = provided or generate_password()
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        return password

    @staticmethod
    def _admin_exists(*, slug: str, email: str) -> bool:
        """Return whether the tenant's schema already holds that administrator.

        Mirrors the condition :func:`apps.tenancy.services.provision_tenant` uses
        to decide whether a password is applied: an administrator that already
        exists keeps its password. This is only a probe to keep the operator
        message honest, so anything it cannot answer means "assume created" and
        the service reports the real problem.

        Args:
            slug: Tenant slug, which is also the schema name.
            email: Administrator email.

        Returns:
            ``True`` when the tenant schema already contains that user.
        """
        if slug == get_public_schema_name() or not schema_exists(slug):
            # The registry schema is not a provisionable client, and a missing
            # schema is about to be created by the service.
            return False

        tenant = models.Tenant.objects.filter(schema_name=slug).first()
        if tenant is None:
            return False

        from apps.users.models import User

        try:
            with tenant_context(tenant):
                return User.objects.filter(email=email).exists()
        except DatabaseError:
            # A registry row may exist before its schema is migrated; the probe
            # is not the place to fail, the service is.
            return False

    @staticmethod
    def _summary(
        tenant: models.Tenant, options: dict[str, Any], password: str | None
    ) -> str:
        """Return the operator summary printed after provisioning.

        Args:
            tenant: The provisioned tenant.
            options: Parsed management options.
            password: The password actually applied to a new administrator, or
                ``None`` when an existing administrator kept its own.

        Returns:
            The multi-line summary.
        """
        domain = tenant.get_primary_domain()
        lines = [
            f"Tenant '{tenant.name}' provisioned.",
            f"- Schema: {tenant.schema_name}",
            f"- Domain: {domain.domain if domain else '-'}",
            f"- Admin: {options['admin_email']}",
        ]
        if password is not None:
            lines.append(f"- Admin password: {password}")
        return "\n".join(lines)
