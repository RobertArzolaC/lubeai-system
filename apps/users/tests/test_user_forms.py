"""Tests for :class:`apps.users.forms.UserManagementForm`."""

from django.test import TestCase

from apps.organizations.factories import OrganizationFactory
from apps.users.factories import RoleFactory, UserFactory
from apps.users.forms import UserManagementForm


class UserManagementFormTests(TestCase):
    """Scoping and field behaviour of the user management form."""

    def setUp(self) -> None:
        self.lab = OrganizationFactory()
        self.child = OrganizationFactory(parent=self.lab)
        self.actor = UserFactory(organization=self.lab)

    def test_roles_queryset_scoped_to_visible_orgs(self) -> None:
        """Only roles in the actor's subtree are offered."""
        own_role = RoleFactory(organization=self.lab)
        child_role = RoleFactory(organization=self.child)
        foreign_role = RoleFactory(organization=OrganizationFactory())

        form = UserManagementForm(user=self.actor)

        self.assertIn(own_role, form.fields["roles"].queryset)
        self.assertIn(child_role, form.fields["roles"].queryset)
        self.assertNotIn(foreign_role, form.fields["roles"].queryset)

    def test_rejects_foreign_organization(self) -> None:
        """Review Focus #3: an org outside the subtree is rejected."""
        foreign = OrganizationFactory()
        form = UserManagementForm(
            {
                "organization": foreign.pk,
                "first_name": "Ana",
                "last_name": "Diaz",
                "email": "ana@example.com",
                "is_active": "on",
            },
            user=self.actor,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("organization", form.errors)

    def test_email_disabled_when_editing(self) -> None:
        """Editing an existing user disables the email field."""
        member = UserFactory(organization=self.lab)
        form = UserManagementForm(instance=member, user=self.actor)
        self.assertTrue(form.fields["email"].disabled)

    def test_preselects_current_roles(self) -> None:
        """The user's current roles are pre-checked."""
        role = RoleFactory(organization=self.lab)
        member = UserFactory(organization=self.lab)
        member.groups.add(role.group)

        form = UserManagementForm(instance=member, user=self.actor)

        self.assertIn(role.pk, [int(value) for value in form["roles"].value()])

    def test_preset_organization_initial(self) -> None:
        """The organization from the query string becomes the initial value."""
        form = UserManagementForm(user=self.actor, organization=self.child.pk)
        self.assertEqual(form.fields["organization"].initial, self.child.pk)
