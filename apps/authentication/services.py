"""Service helpers for authentication flows."""

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError


def get_password_checks(
    password: str | None, user: AbstractBaseUser | None = None
) -> list[dict]:
    """
    Evaluate ``password`` against every configured password validator.

    Args:
        password: The candidate password, or ``None``/empty when no input yet.
        user: The user whose password is being validated (used by similarity checks).

    Returns:
        One dict per configured validator with keys ``id`` (validator class
        name), ``label`` (human-readable help text) and ``passed`` (bool).
    """
    checks: list[dict] = []
    validators = password_validation.get_password_validators(
        settings.AUTH_PASSWORD_VALIDATORS
    )
    for validator in validators:
        passed = False
        if password:
            try:
                validator.validate(password, user=user)
                passed = True
            except ValidationError:
                passed = False
        checks.append(
            {
                "id": validator.__class__.__name__,
                "label": validator.get_help_text(),
                "passed": passed,
            }
        )
    return checks
