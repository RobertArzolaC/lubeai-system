"""Tests for the ``apps.users.mixins`` module."""

from django import forms
from django.contrib.auth.models import Permission
from django.test import TestCase

from apps.users import mixins
from apps.users import models as users_models
from apps.users.factories import UserFactory


class PermissionTestForm(mixins.PermissionFormMixin, forms.ModelForm):
    """Concrete form used to exercise the :class:`PermissionFormMixin`."""

    class Meta:
        model = users_models.Account
        fields: tuple[str, ...] = ()


class PermissionFormMixinTests(TestCase):
    """Tests for the :class:`PermissionFormMixin`."""

    def setUp(self) -> None:
        self.user = UserFactory()

    def test_permission_fields_created(self) -> None:
        """The form exposes the four CRUD permission checkboxes."""
        form = PermissionTestForm()
        for action in ("view", "add", "change", "delete"):
            field_name = f"can_{action}_account"
            self.assertIn(field_name, form.fields)
            self.assertIsInstance(form.fields[field_name], forms.BooleanField)

    def test_initial_permission_from_instance_user(self) -> None:
        """Initial checkbox state reflects the linked user permissions."""
        permission = Permission.objects.get(codename="view_account")
        self.user.user_permissions.add(permission)
        account = self.user.account
        form = PermissionTestForm(instance=account)
        self.assertTrue(form.fields["can_view_account"].initial)

    def test_save_permissions_grants_checked_fields(self) -> None:
        """Checked permissions are granted to the given user."""
        form = PermissionTestForm(data={"can_add_account": "on"})
        self.assertTrue(form.is_valid())
        form.save_permissions(self.user)
        self.assertTrue(self.user.has_perm("users.add_account"))
        self.assertFalse(self.user.has_perm("users.delete_account"))

    def test_save_permissions_removes_unchecked_fields(self) -> None:
        """Unchecked permissions are removed from the given user."""
        permissions = Permission.objects.filter(
            codename__in=["add_account", "delete_account"]
        )
        self.user.user_permissions.add(*permissions)
        form = PermissionTestForm(data={})
        self.assertTrue(form.is_valid())
        form.save_permissions(self.user)
        self.assertFalse(self.user.has_perm("users.add_account"))
        self.assertFalse(self.user.has_perm("users.delete_account"))
