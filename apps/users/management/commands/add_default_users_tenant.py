"""Create the default users of one tenant schema.

This command is meant to be called through
:mod:`apps.users.management.commands.add_default_users`, which selects a schema
before handing over control.

The password is never hard-coded: it comes from ``--password``, is validated
with Django's configured validators, and when omitted a random one is generated
and printed **once**. A repository default would let anyone stand up an
administrator with a publicly known password in every tenant schema.
"""

from __future__ import annotations

from typing import Any

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.organizations.models import Organization
from apps.organizations.services import OrganizationService, RootOrganizationError
from apps.tenancy.management.commands.provision_tenant import generate_password
from apps.users.models import User


class Command(BaseCommand):
    """Generate the default users: one superuser and two staff users."""

    help = "Generates default users including superuser and staff users"

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command options.

        Args:
            parser: The command's argument parser.
        """
        parser.add_argument(
            "--password",
            default=None,
            help=(
                "Password for the created users, validated with Django's "
                "configured validators. A random one is generated and printed "
                "once when omitted."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Create every default user, skipping the ones that already exist.

        Args:
            *args: Unused positional arguments.
            **options: Parsed management options.

        Raises:
            CommandError: If the password fails Django's configured validators,
                or the tenant schema has more than one root organization.
        """
        password, generated = self._resolve_password(options.get("password"))

        superuser_data = {
            "email": "admin@example.com",
            "first_name": "Administrator",
            "last_name": "Principal",
            "is_staff": True,
            "is_superuser": True,
        }

        staff_users_data = [
            {
                "email": "staff1@example.com",
                "first_name": "Staff 1",
                "last_name": "Manager",
                "is_staff": True,
            },
            {
                "email": "staff2@example.com",
                "first_name": "Staff 2",
                "last_name": "Validator",
                "is_staff": True,
            },
        ]

        users_created = 0
        users_existed = 0

        superuser = self.create_user(
            superuser_data, password, self.get_default_organization()
        )
        if superuser:
            users_created += 1
            self.stdout.write(
                self.style.SUCCESS(f"Superuser created successfully: {superuser.email}")
            )
        else:
            users_existed += 1
            self.stdout.write(
                self.style.WARNING(
                    f"Superuser already exists: {superuser_data['email']}"
                )
            )

        for staff_data in staff_users_data:
            staff_user = self.create_user(
                staff_data, password, self.get_default_organization()
            )
            if staff_user:
                users_created += 1
                self.assign_staff_permissions(staff_user)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Staff user created successfully: {staff_user.email}"
                    )
                )
            else:
                users_existed += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Staff user already exists: {staff_data['email']}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nProcess completed:\n"
                f"- Users created: {users_created}\n"
                f"- Users already existed: {users_existed}\n"
                f"- Total users processed: {users_created + users_existed}"
            )
        )
        if generated:
            self.stdout.write(
                self.style.WARNING(
                    f"Generated password (shown once): {password}"
                )
            )

    @staticmethod
    def _resolve_password(provided: str | None) -> tuple[str, bool]:
        """Return a validated password and whether it was generated.

        There is no repository default: a publicly known password must never be
        able to create a superuser, which is why the value is validated with the
        same validators the tenant console and ``provision_tenant`` use.

        Args:
            provided: Password from ``--password``, if any.

        Returns:
            A ``(password, generated)`` pair; ``generated`` is ``True`` when the
            caller omitted the option and a random password was drawn.

        Raises:
            CommandError: If the password fails Django's configured validators.
        """
        generated = provided is None
        password = provided or generate_password()
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        return password, generated

    def create_user(
        self,
        user_data: dict[str, Any],
        password: str,
        organization: Organization | None = None,
    ) -> User | None:
        """Create the user described by ``user_data``, unless it exists.

        Args:
            user_data: User fields; ``email`` identifies the user.
            password: Password to set on a newly created user.
            organization: Organization the user belongs to, if any.

        Returns:
            The created user, or ``None`` when the email was already taken.
        """
        user_data = user_data.copy()
        email = user_data.pop("email")
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create_user(
                email=email, password=password, organization=organization, **user_data
            )

            EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                primary=True,
                verified=True,
            )
            return user

        return None

    def get_default_organization(self) -> Organization | None:
        """Return the root organization provisioned for the current tenant.

        ``provision_tenant`` creates the tenant's root organization; this
        command must reuse it instead of creating a second organization with a
        hard-coded name. A schema that has not been provisioned has no root, so
        the users are created without an organization.

        Returns:
            The tenant's root organization, or ``None`` when it is missing.

        Raises:
            CommandError: If the schema holds more than one root organization,
                because attaching the users to an arbitrary one would be wrong.
        """
        try:
            return OrganizationService.resolve_root(required=False)
        except RootOrganizationError as error:
            raise CommandError(str(error)) from error

    def assign_staff_permissions(self, user: User) -> None:
        """Grant the staff user the permissions the platform manages with.

        Args:
            user: The staff user to grant permissions to.
        """
        result_permissions = Permission.objects.filter(
            codename__in=[
                "view_report",
                "add_report",
                "change_report",
                "view_analysisthreshold",
                "view_component_analysis",
                "view_alert",
                "change_alert",
                "view_machine",
                "view_branch",
                "view_componenttype",
            ]
        )
        user.user_permissions.add(*result_permissions)
