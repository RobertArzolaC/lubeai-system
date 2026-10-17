"""Tests for the user admin organization assignment."""

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.organizations import choices as org_choices
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
        """The changelist lists the organization and offers a scoped filter."""
        self.assertIn("organization", self.model_admin.list_display)
        self.assertIn(users_admin.OrganizationListFilter, self.model_admin.list_filter)


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


class UserAdminOrganizationScopeTests(TestCase):
    """The assignable organizations follow the acting user subtree."""

    def setUp(self) -> None:
        """Build a model admin and the tenant tree."""
        self.site = AdminSite()
        self.model_admin = users_admin.CustomUserAdmin(users_models.User, self.site)
        self.tenant = org_factories.OrganizationFactory(
            slug="adm-tenant", kind=org_choices.OrganizationKind.LAB
        )
        self.child = org_factories.OrganizationFactory(
            slug="adm-child",
            kind=org_choices.OrganizationKind.FINAL,
            parent=self.tenant,
        )
        self.outsider = org_factories.OrganizationFactory(
            slug="adm-outsider", kind=org_choices.OrganizationKind.LAB
        )

    def field_organization_ids(self, user) -> set[int]:
        """Return the organization ids offered by the admin field."""
        request = RequestFactory().get("/admin/users/user/")
        request.user = user
        field = self.model_admin.formfield_for_foreignkey(
            users_models.User._meta.get_field("organization"), request
        )
        return set(field.queryset.values_list("id", flat=True))

    def test_scoped_staff_sees_only_its_subtree(self) -> None:
        """A staff user with an organization sees it and its descendants."""
        staff = UserFactory(is_staff=True, organization=self.tenant)
        self.assertEqual(
            self.field_organization_ids(staff), {self.tenant.id, self.child.id}
        )

    def test_superuser_sees_every_organization(self) -> None:
        """A superuser is unrestricted."""
        admin = UserFactory(is_staff=True, is_superuser=True)
        ids = self.field_organization_ids(admin)
        self.assertIn(self.outsider.id, ids)
        self.assertIn(self.tenant.id, ids)


class UserAdminScopedActorTests(TestCase):
    """A scoped staff actor cannot widen or erase tenancy through the admin."""

    def setUp(self) -> None:
        """Build the tenant tree and two scoped staff actors."""
        self.site = AdminSite()
        self.model_admin = users_admin.CustomUserAdmin(users_models.User, self.site)
        self.tenant = org_factories.OrganizationFactory(
            slug="sa-tenant", kind=org_choices.OrganizationKind.LAB
        )
        self.child = org_factories.OrganizationFactory(
            slug="sa-child",
            kind=org_choices.OrganizationKind.FINAL,
            parent=self.tenant,
        )
        self.outsider = org_factories.OrganizationFactory(
            slug="sa-outsider", kind=org_choices.OrganizationKind.LAB
        )
        permissions = Permission.objects.filter(
            codename__in=["view_user", "change_user", "add_user"]
        )
        # A multi-organization actor (tenant + child) and a leaf actor (child).
        self.actor = UserFactory(is_staff=True, organization=self.tenant)
        self.actor.user_permissions.add(*permissions)
        self.leaf = UserFactory(is_staff=True, organization=self.child)
        self.leaf.user_permissions.add(*permissions)

    def admin_request(self, user):
        """Return a request whose user is the given actor."""
        request = RequestFactory().get("/admin/users/user/")
        request.user = user
        return request

    def test_out_of_subtree_change_preserves_organization(self) -> None:
        """Submitting an empty selection never clears another branch's owner."""
        self.client.force_login(self.actor)
        target = UserFactory(organization=self.outsider)
        response = self.client.post(
            reverse("admin:users_user_change", args=[target.pk]),
            {"email": target.email, "is_active": "on", "organization": ""},
        )
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.organization, self.outsider)

    def test_add_without_organization_creates_unassigned_user(self) -> None:
        """Leaving the organization empty on add stores a null organization."""
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("admin:users_user_add"),
            {
                "email": "scoped-new@example.com",
                "password1": "Sup3rSecret!42",
                "password2": "Sup3rSecret!42",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = users_models.User.objects.get(email="scoped-new@example.com")
        self.assertIsNone(user.organization)

    def test_leaf_actor_organization_field_is_disabled(self) -> None:
        """A single-organization actor cannot reassign the organization."""
        form_class = self.model_admin.get_form(
            self.admin_request(self.leaf),
            obj=UserFactory(organization=self.outsider),
        )
        self.assertTrue(form_class().fields["organization"].disabled)

    def test_leaf_actor_has_no_organization_filter(self) -> None:
        """A single-organization actor gets no organization filter."""
        self.assertNotIn(
            users_admin.OrganizationListFilter,
            self.model_admin.get_list_filter(self.admin_request(self.leaf)),
        )

    def test_chooser_organization_filter_is_scoped(self) -> None:
        """The organization filter only offers the actor's subtree."""
        request = self.admin_request(self.actor)
        self.assertIn(
            users_admin.OrganizationListFilter,
            self.model_admin.get_list_filter(request),
        )
        list_filter = users_admin.OrganizationListFilter(
            request, {}, users_models.User, self.model_admin
        )
        self.assertEqual(
            {value for value, _label in list_filter.lookup_choices},
            {self.tenant.id, self.child.id},
        )
