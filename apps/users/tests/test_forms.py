"""Tests for the ``apps.users.forms`` module."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from apps.organizations import factories as organization_factories
from apps.users import constants as users_constants
from apps.users import forms as users_forms
from apps.users.factories import RoleFactory, UserFactory
from apps.users.tests.base import UserTenantTestCase

User = get_user_model()


class CustomUserCreationFormTests(TestCase):
    """Tests for :class:`CustomUserCreationForm`."""

    def test_meta_model_is_user(self) -> None:
        """The form targets the custom User model with the email field."""
        self.assertEqual(users_forms.CustomUserCreationForm.Meta.model, User)
        self.assertEqual(users_forms.CustomUserCreationForm.Meta.fields, ("email",))

    def test_creation_fields_present(self) -> None:
        """Email and password fields are exposed by the form."""
        form = users_forms.CustomUserCreationForm()
        self.assertIn("email", form.fields)
        self.assertIn("password1", form.fields)
        self.assertIn("password2", form.fields)


class CustomUserChangeFormTests(TestCase):
    """Tests for :class:`CustomUserChangeForm`."""

    def test_meta_model_is_user(self) -> None:
        """The form targets the custom User model with the email field."""
        self.assertEqual(users_forms.CustomUserChangeForm.Meta.model, User)
        self.assertEqual(users_forms.CustomUserChangeForm.Meta.fields, ("email",))


class UserSettingsFormTests(UserTenantTestCase):
    """Tests for :class:`UserSettingsForm`."""

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory(first_name="Old", last_name="Name")

    def test_valid_data_updates_user(self) -> None:
        """Valid data updates the user first and last names."""
        form = users_forms.UserSettingsForm(
            data={"first_name": "New", "last_name": "Person"},
            instance=self.user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Person")

    def test_last_name_is_optional(self) -> None:
        """A missing last name is accepted by the form."""
        form = users_forms.UserSettingsForm(
            data={"first_name": "Only"}, instance=self.user
        )
        self.assertTrue(form.is_valid())


class RoleFormPermissionCatalogTests(UserTenantTestCase):
    """The role form only offers dashboard permissions with readable labels."""

    def setUp(self) -> None:
        super().setUp()
        self.organization = organization_factories.OrganizationFactory()
        self.user = UserFactory(organization=self.organization)
        self.form = users_forms.RoleForm(user=self.user)

    def test_only_dashboard_modules_are_offered(self) -> None:
        """The permission queryset is limited to the dashboard app labels."""
        app_labels = set(
            self.form.fields["permissions"].queryset.values_list(
                "content_type__app_label", flat=True
            )
        )
        self.assertEqual(app_labels, set(users_constants.ROLE_PERMISSION_MODULES))

    def test_system_permissions_are_rejected(self) -> None:
        """A tampered POST with an auth permission is invalid."""
        permission = Permission.objects.get(
            content_type__app_label="auth", codename="add_group"
        )
        form = users_forms.RoleForm(
            data={
                "organization": self.organization.pk,
                "name": "Analista",
                "description": "",
                "is_active": "on",
                "permissions": [permission.pk],
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("permissions", form.errors)

    def test_permission_labels_are_human_readable(self) -> None:
        """Standard and custom permissions get Spanish labels."""
        labels = [
            permission["label"]
            for group in self.form.permission_groups
            for permission in group["permissions"]
        ]
        self.assertIn("Ver Máquina", labels)
        self.assertIn("Puede ver el análisis de componentes", labels)

    def test_permission_modules_keep_the_dashboard_order(self) -> None:
        """Modules follow the menu order, not the alphabetical app order."""
        self.assertEqual(
            [module["label"] for module in self.form.permission_modules],
            ["Equipos", "Informes", "Alertas", "Clientes", "Cuentas y accesos"],
        )

    def test_selected_permission_ids_is_cached(self) -> None:
        """The selected ids are queried once per form instance, not per checkbox."""
        role = RoleFactory(organization=self.organization)
        form = users_forms.RoleForm(instance=role, user=self.user)
        with self.assertNumQueries(1):
            first = form.selected_permission_ids
        with self.assertNumQueries(0):
            second = form.selected_permission_ids
        self.assertEqual(first, second)
