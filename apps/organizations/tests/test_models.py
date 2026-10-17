"""Tests for the Organization model."""

from django.test import TestCase

from apps.organizations import choices, models


class OrganizationTests(TestCase):
    """The tenancy tree, branding inheritance and capabilities."""

    def setUp(self) -> None:
        """Build a small tenancy tree: root -> intermediary -> final."""
        self.marco = models.Organization.objects.create(
            name="MARCO",
            slug="root-tenant",
            kind=choices.OrganizationKind.LAB,
        )
        self.intermediary = models.Organization.objects.create(
            name="Intermediario A",
            slug="intermediario-a",
            kind=choices.OrganizationKind.INTERMEDIARY,
            parent=self.marco,
        )
        self.final = models.Organization.objects.create(
            name="Final A1",
            slug="final-a1",
            kind=choices.OrganizationKind.FINAL,
            parent=self.intermediary,
        )

    def test_root_is_tenant(self) -> None:
        """A node without parent is a tenant."""
        self.assertTrue(self.marco.is_tenant)
        self.assertFalse(self.final.is_tenant)

    def test_tenant_resolves_to_root(self) -> None:
        """A nested node resolves its tenant to the root ancestor."""
        self.assertEqual(self.final.tenant, self.marco)
        self.assertEqual(self.intermediary.tenant, self.marco)

    def test_descendants_include_self_and_children(self) -> None:
        """Descendants traverse the whole subtree."""
        ids = set(self.marco.descendants(include_self=True).values_list("id", flat=True))
        self.assertEqual(ids, {self.marco.id, self.intermediary.id, self.final.id})

    def test_branding_is_inherited_from_ancestor(self) -> None:
        """A child inherits branding slots it does not define."""
        self.marco.chart_danger = "#ff0000"
        self.marco.save(update_fields=["chart_danger"])
        self.assertEqual(self.final.get_branding()["chart_danger"], "#ff0000")

    def test_branding_child_overrides_ancestor(self) -> None:
        """A child's own branding slot wins over the ancestor's."""
        self.marco.chart_danger = "#ff0000"
        self.marco.save(update_fields=["chart_danger"])
        self.final.chart_danger = "#00ff00"
        self.final.save(update_fields=["chart_danger"])
        self.assertEqual(self.final.get_branding()["chart_danger"], "#00ff00")

    def test_branding_falls_back_to_default(self) -> None:
        """With no branding anywhere, the default palette is used."""
        self.assertEqual(
            self.marco.get_branding()["primary_color"],
            models.constants.DEFAULT_BRANDING["primary_color"],
        )

    def test_capabilities_default_by_kind(self) -> None:
        """Capabilities default from the tenant kind."""
        self.assertFalse(self.marco.has_capability("labs"))
        self.assertTrue(self.marco.has_capability("analysis"))

    def test_capabilities_can_be_overridden(self) -> None:
        """A per-organization override wins over the kind default."""
        self.marco.capabilities = {"labs": True}
        self.marco.save(update_fields=["capabilities"])
        self.assertTrue(self.marco.has_capability("labs"))
