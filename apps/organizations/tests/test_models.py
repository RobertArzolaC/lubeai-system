"""Tests for the Organization model."""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from apps.organizations import choices, factories, models
from apps.organizations.tests.base import OrganizationTenantTestCase
from apps.tenancy import choices as tenancy_choices
from apps.tenancy import models as tenancy_models


class OrganizationTests(OrganizationTenantTestCase):
    """The tenancy tree, branding inheritance and capabilities."""

    def setUp(self) -> None:
        """Build a small tree: root -> intermediary -> final."""
        super().setUp()
        self.root = models.Organization.objects.create(
            name="MARCO",
            slug="root-tenant",
            kind=choices.OrganizationKind.LAB,
        )
        self.intermediary = models.Organization.objects.create(
            name="Intermediario A",
            slug="intermediario-a",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.root,
        )
        self.final = models.Organization.objects.create(
            name="Final A1",
            slug="final-a1",
            kind=choices.OrganizationKind.FINAL,
            parent=self.intermediary,
        )

    def test_root_is_tenant(self) -> None:
        """The node without a parent is the tenant's root organization."""
        self.assertTrue(self.root.is_tenant)
        self.assertFalse(self.final.is_tenant)

    def test_tenant_resolves_to_root(self) -> None:
        """A nested node resolves its tenant to the root ancestor."""
        self.assertEqual(self.final.tenant, self.root)
        self.assertEqual(self.intermediary.tenant, self.root)

    def test_descendants_include_self_and_children(self) -> None:
        """Descendants traverse the whole subtree."""
        ids = set(self.root.descendants(include_self=True).values_list("id", flat=True))
        self.assertEqual(ids, {self.root.id, self.intermediary.id, self.final.id})

    def test_branding_is_inherited_from_ancestor(self) -> None:
        """A child inherits branding slots it does not define."""
        self.root.chart_danger = "#ff0000"
        self.root.save(update_fields=["chart_danger"])
        self.assertEqual(self.final.get_branding()["chart_danger"], "#ff0000")

    def test_branding_child_overrides_ancestor(self) -> None:
        """A child's own branding slot wins over the ancestor's."""
        self.root.chart_danger = "#ff0000"
        self.root.save(update_fields=["chart_danger"])
        self.final.chart_danger = "#00ff00"
        self.final.save(update_fields=["chart_danger"])
        self.assertEqual(self.final.get_branding()["chart_danger"], "#00ff00")

    def test_branding_falls_back_to_default(self) -> None:
        """With no branding anywhere, the default palette is used."""
        self.assertEqual(
            self.root.get_branding()["primary_color"],
            models.constants.DEFAULT_BRANDING["primary_color"],
        )

    def test_capabilities_default_by_kind(self) -> None:
        """Capabilities default from the tenant kind."""
        self.assertFalse(self.root.has_capability("labs"))
        self.assertTrue(self.root.has_capability("analysis"))

    def test_capabilities_can_be_overridden(self) -> None:
        """A per-organization override wins over the kind default."""
        self.root.capabilities = {"labs": True}
        self.root.save(update_fields=["capabilities"])
        self.assertTrue(self.root.has_capability("labs"))

    def test_slug_unique_within_schema(self) -> None:
        """Slugs are unique inside a tenant's schema, not globally."""
        factories.OrganizationFactory(slug="planta-norte")
        with self.assertRaises(IntegrityError), transaction.atomic():
            factories.OrganizationFactory(slug="planta-norte")


class SlugPerSchemaTests(OrganizationTenantTestCase):
    """The same slug may exist in two tenants, one schema each."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create a second tenant next to the one the base class builds."""
        super().setUpClass()
        connection.set_schema_to_public()
        cls.other_tenant = tenancy_models.Tenant.objects.create(
            name="Other tenant",
            slug="organizations-other",
            kind=tenancy_choices.TenantKind.LAB,
        )
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls) -> None:
        """Drop the extra schema and tenant row before the base cleanup."""
        connection.set_schema_to_public()
        cls.other_tenant.delete(force_drop=True)
        super().tearDownClass()

    def test_same_slug_is_allowed_in_another_tenant(self) -> None:
        """A slug taken in one schema is free in another schema."""
        models.Organization.objects.create(name="Planta Norte", slug="planta-norte")

        connection.set_tenant(self.other_tenant)
        try:
            other = models.Organization.objects.create(
                name="Planta Norte", slug="planta-norte"
            )
            self.assertEqual(other.slug, "planta-norte")
        finally:
            connection.set_tenant(self.tenant)

        self.assertTrue(
            models.Organization.objects.filter(slug="planta-norte").exists()
        )


class OrganizationSettingsTests(TestCase):
    """The organizations app lives in every tenant schema."""

    def test_organizations_is_a_tenant_app(self) -> None:
        """``apps.organizations`` is migrated per tenant, never into public."""
        self.assertIn("apps.organizations", settings.TENANT_APPS)
        self.assertNotIn("apps.organizations", settings.SHARED_APPS)
