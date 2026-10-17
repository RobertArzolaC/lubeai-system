"""Tests for branding services, tenant middleware and context processors."""

from django.test import RequestFactory, TestCase, override_settings

from apps.organizations import (
    choices,
    constants,
    context_processors,
    factories,
    middleware,
    models,
    services,
)


class ColorPaletteServiceTests(TestCase):
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


class TenantMiddlewareTests(TestCase):
    """The middleware resolves the tenant from host then default slug."""

    def setUp(self) -> None:
        """Create a test tenant and a request factory."""
        self.factory = RequestFactory()
        self.tenant = factories.OrganizationFactory(
            slug="acme", kind=choices.OrganizationKind.LAB
        )

    @override_settings(TENANT_BASE_DOMAIN="example.com", DEFAULT_TENANT_SLUG=None)
    def test_resolves_tenant_from_subdomain(self) -> None:
        """A subdomain matching an organization slug resolves the tenant."""
        request = self.factory.get("/", HTTP_HOST="acme.example.com")
        middleware.TenantMiddleware(lambda r: r)(request)
        self.assertEqual(request.tenant, self.tenant)

    @override_settings(TENANT_BASE_DOMAIN="example.com", DEFAULT_TENANT_SLUG=None)
    def test_unknown_subdomain_has_no_tenant(self) -> None:
        """An unknown subdomain resolves to no tenant."""
        request = self.factory.get("/", HTTP_HOST="nope.example.com")
        middleware.TenantMiddleware(lambda r: r)(request)
        self.assertIsNone(request.tenant)

    @override_settings(TENANT_BASE_DOMAIN="", DEFAULT_TENANT_SLUG="acme")
    def test_falls_back_to_default_slug(self) -> None:
        """The default slug is used for local/unknown hosts."""
        request = self.factory.get("/", HTTP_HOST="localhost")
        middleware.TenantMiddleware(lambda r: r)(request)
        self.assertEqual(request.tenant, self.tenant)


class BrandingContextProcessorTests(TestCase):
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


class MarcoDataMigrationTests(TestCase):
    """The data migration creates the MARCO root tenant."""

    def test_marco_tenant_exists(self) -> None:
        """A tenant with slug ``marco`` is created by the migration."""
        self.assertTrue(
            models.Organization.objects.filter(
                slug="marco", kind=choices.OrganizationKind.LAB
            ).exists()
        )
