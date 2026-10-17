"""Tests for organization scoping on the account views."""

from django.contrib.auth.models import Permission
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories
from apps.users import forms
from apps.users import views as user_views


class AccountListViewScopingTests(TestCase):
    """The account list is restricted to the user's subtree."""

    def setUp(self) -> None:
        """Create two tenants, each with an account and a manager user."""
        self.tenant_a = organization_factories.OrganizationFactory(
            slug="acct-a", kind=choices.OrganizationKind.INTERMEDIARY
        )
        self.tenant_b = organization_factories.OrganizationFactory(
            slug="acct-b", kind=choices.OrganizationKind.INTERMEDIARY
        )
        self.account_a = user_factories.AccountFactory(
            user=user_factories.UserFactory(organization=self.tenant_a)
        )
        self.account_b = user_factories.AccountFactory(
            user=user_factories.UserFactory(organization=self.tenant_b)
        )
        self.manager = self._manager(self.tenant_a)

    @staticmethod
    def _manager(organization):
        """Return a user with ``view_account`` scoped to ``organization``."""
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        user.user_permissions.add(*Permission.objects.filter(codename="view_account"))
        return user

    def _queryset_ids(self, user):
        """Return the account ids the list view would expose to ``user``."""
        view = user_views.AccountListView()
        view.request = RequestFactory().get("/")
        view.request.user = user
        return set(view.get_queryset().values_list("id", flat=True))

    def test_manager_only_sees_own_accounts(self) -> None:
        """A tenant manager does not see another tenant's accounts."""
        ids = self._queryset_ids(self.manager)
        self.assertIn(self.account_a.id, ids)
        self.assertNotIn(self.account_b.id, ids)

    def test_superuser_sees_all_accounts(self) -> None:
        """A superuser sees every account."""
        superuser = user_factories.UserFactory(is_superuser=True)
        ids = self._queryset_ids(superuser)
        self.assertIn(self.account_a.id, ids)
        self.assertIn(self.account_b.id, ids)


class AccountCreationScopingTests(TestCase):
    """New accounts inherit the creator's organization."""

    def test_created_account_inherits_organization(self) -> None:
        """The created user belongs to the creator's organization."""
        organization = organization_factories.OrganizationFactory(slug="acct-create")
        creator = user_factories.UserFactory()
        creator.organization = organization
        creator.save(update_fields=["organization"])

        request = RequestFactory().post("/")
        request.session = SessionStore()
        request.user = creator
        form = forms.AccountCreationForm(
            data={
                "email": "nuevo@example.com",
                "first_name": "N",
                "last_name": "U",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(request)
        self.assertEqual(user.organization_id, organization.id)
