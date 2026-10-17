"""Tests for the user admin organization assignment."""

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.organizations import factories as org_factories
from apps.users import admin as users_admin
from apps.users import models as users_models
from apps.users.factories import UserFactory


class UserAdminOrganizationFieldTests(TestCase):
    """The admin exposes the ``organization`` field on add and change forms."""

    def setUp(self) -> None:
        """Build a model admin and an admin request."""
        self.site = AdminSite()
        self.model_admin = users_admin.CustomUserAdmin(users_models.User, self.site)
        self.request = RequestFactory().get("/admin/users/user/")
        self.request.user = UserFactory(is_staff=True, is_superuser=True)

    def test_change_form_exposes_organization(self) -> None:
        """The change form includes the organization field."""
        target = UserFactory()
        form_class = self.model_admin.get_form(self.request, obj=target)
        self.assertIn("organization", form_class.base_fields)

    def test_add_form_exposes_organization(self) -> None:
        """The add form includes the organization field."""
        form_class = self.model_admin.get_form(self.request)
        self.assertIn("organization", form_class.base_fields)

    def test_add_form_organization_is_optional(self) -> None:
        """Leaving the organization empty is allowed."""
        form_class = self.model_admin.get_form(self.request)
        self.assertFalse(form_class.base_fields["organization"].required)

    def test_changelist_shows_organization(self) -> None:
        """The changelist lists and filters by organization."""
        self.assertIn("organization", self.model_admin.list_display)
        self.assertIn("organization", self.model_admin.list_filter)


class UserAdminOrganizationSaveTests(TestCase):
    """Saving through the admin persists the organization."""

    def setUp(self) -> None:
        """Log an admin in and build a target organization."""
        self.admin = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.organization = org_factories.OrganizationFactory(slug="adm-save")

    def test_add_view_assigns_organization(self) -> None:
        """An add persists the selected organization."""
        response = self.client.post(
            reverse("admin:users_user_add"),
            {
                "email": "withorg@example.com",
                "password1": "Sup3rSecret!42",
                "password2": "Sup3rSecret!42",
                "is_active": "on",
                "organization": self.organization.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        user = users_models.User.objects.get(email="withorg@example.com")
        self.assertEqual(user.organization, self.organization)

    def test_change_view_assigns_organization(self) -> None:
        """A change persists the selected organization."""
        target = UserFactory()
        response = self.client.post(
            reverse("admin:users_user_change", args=[target.pk]),
            {
                "email": target.email,
                "is_active": "on",
                "organization": self.organization.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.organization, self.organization)
