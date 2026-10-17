"""Tests for organization scoping of alert notifications."""

from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase

from apps.alerts import factories as alert_factories
from apps.alerts.services.notifications import AlertNotificationService
from apps.organizations import choices
from apps.organizations import factories as organization_factories
from apps.users import factories as user_factories


class AlertNotificationScopingTests(TestCase):
    """Alert emails never cross the tenant that owns the alert."""

    def setUp(self) -> None:
        """Two tenants; an alert owned by a final client of tenant A."""
        self.tenant_a = organization_factories.OrganizationFactory(
            slug="n-a", kind=choices.OrganizationKind.LAB
        )
        self.tenant_b = organization_factories.OrganizationFactory(
            slug="n-b", kind=choices.OrganizationKind.LAB
        )
        self.final_a = organization_factories.OrganizationFactory(
            slug="n-a-final",
            kind=choices.OrganizationKind.FINAL,
            parent=self.tenant_a,
        )
        self.final_b = organization_factories.OrganizationFactory(
            slug="n-b-final",
            kind=choices.OrganizationKind.FINAL,
            parent=self.tenant_b,
        )
        self.alert_a = alert_factories.AlertFactory(organization=self.final_a)

        self.user_a_final = self._permissioned_user(self.final_a)
        self.user_a_root = self._permissioned_user(self.tenant_a)
        self.user_b_final = self._permissioned_user(self.final_b)

    @staticmethod
    def _permissioned_user(organization):
        """Return a user with ``view_alert`` in ``organization``."""
        user = user_factories.UserFactory()
        user.organization = organization
        user.save(update_fields=["organization"])
        user.user_permissions.add(*Permission.objects.filter(codename="view_alert"))
        return user

    def _recipient_emails(self) -> set[str]:
        """Return the set of emails the last send produced."""
        return {message.to[0] for message in mail.outbox}

    def test_owner_and_ancestors_are_notified(self) -> None:
        """The alert's organization and its ancestors within the tenant get it."""
        mail.outbox.clear()
        AlertNotificationService([self.alert_a.pk]).send()
        recipients = self._recipient_emails()
        self.assertIn(self.user_a_final.email, recipients)
        self.assertIn(self.user_a_root.email, recipients)

    def test_other_tenant_is_never_notified(self) -> None:
        """A user of another tenant does not receive the alert."""
        mail.outbox.clear()
        AlertNotificationService([self.alert_a.pk]).send()
        self.assertNotIn(self.user_b_final.email, self._recipient_emails())

    def test_users_without_permission_are_not_notified(self) -> None:
        """A user without ``view_alert`` is skipped."""
        user = user_factories.UserFactory()
        user.organization = self.final_a
        user.save(update_fields=["organization"])
        mail.outbox.clear()
        AlertNotificationService([self.alert_a.pk]).send()
        self.assertNotIn(user.email, self._recipient_emails())

    def test_alert_without_organization_is_not_emailed(self) -> None:
        """An alert with no organization sends nothing."""
        alert = alert_factories.AlertFactory(organization=None)
        mail.outbox.clear()
        result = AlertNotificationService([alert.pk]).send()
        self.assertEqual(result["email"]["sent"], 0)
        self.assertEqual(len(mail.outbox), 0)
