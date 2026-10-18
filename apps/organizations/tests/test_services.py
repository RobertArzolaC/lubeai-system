"""Tests for branding services and context processors."""

from __future__ import annotations

from django.test import RequestFactory

from apps.organizations import constants, context_processors, factories, services
from apps.organizations.tests.base import OrganizationTenantTestCase


class ColorPaletteServiceTests(OrganizationTenantTestCase):
    """The palette service resolves branded or default colors."""

    def test_default_palette_without_organization(self) -> None:
        """Without an organization the default palette is returned."""
        palette = services.ColorPaletteService.get_palette(None)
        self.assertEqual(
            palette["chart_danger"], constants.DEFAULT_BRANDING["chart_danger"]
        )

    def test_organization_palette_overrides(self) -> None:
        """An organization's branded color wins over the default."""
        organization = factories.OrganizationFactory(chart_danger="#123456")
        palette = services.ColorPaletteService.get_palette(organization)
        self.assertEqual(palette["chart_danger"], "#123456")


class BrandingContextProcessorTests(OrganizationTenantTestCase):
    """The branding context processor exposes brand data to templates."""

    def test_branding_from_request_organization(self) -> None:
        """The organization on the request drives the branding context."""
        organization = factories.OrganizationFactory(
            slug="branded", primary_color="#abcdef"
        )
        request = RequestFactory().get("/")
        request.organization = organization
        request.tenant = organization

        context = context_processors.branding(request)
        self.assertEqual(context["current_organization"], organization)
        self.assertEqual(context["branding"]["primary_color"], "#abcdef")

    def test_branding_defaults_without_organization(self) -> None:
        """Without an organization the default branding is used."""
        request = RequestFactory().get("/")
        context = context_processors.branding(request)
        self.assertIsNone(context["current_organization"])
        self.assertEqual(
            context["branding"]["primary_color"],
            constants.DEFAULT_BRANDING["primary_color"],
        )
        self.assertIsNone(context["branding"]["logo"])
