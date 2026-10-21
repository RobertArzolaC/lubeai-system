"""Tests for the provider connection guides."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.integrations.providers import provider_guides

MCP_URL = "https://demo.test/mcp"


class ProviderGuideTests(SimpleTestCase):
    """The catalog is the single source for the connection steps."""

    def test_guides_are_ordered_and_complete(self) -> None:
        """ChatGPT, Claude and Gemini are present with steps and docs."""
        guides = provider_guides(MCP_URL)
        self.assertEqual(
            [guide.slug for guide in guides], ["chatgpt", "claude", "gemini"]
        )
        for guide in guides:
            self.assertTrue(guide.name)
            self.assertTrue(guide.summary)
            self.assertTrue(guide.steps)
            self.assertTrue(guide.docs_url.startswith("https://"))

    def test_url_is_injected_in_every_guide(self) -> None:
        """The tenant MCP URL appears in every provider's fields."""
        guides = provider_guides(MCP_URL)
        for guide in guides:
            values = [
                field.value
                for step in guide.steps
                for field in step.fields
                if field.copyable
            ]
            self.assertIn(MCP_URL, values)

    def test_provider_steps_match_the_documented_menus(self) -> None:
        """Each guide contains the labels verified in the provider UI."""
        guides = {guide.slug: guide for guide in provider_guides(MCP_URL)}

        chatgpt = " ".join(str(step.title) for step in guides["chatgpt"].steps)
        self.assertIn("Complementos", chatgpt)
        self.assertIn("Agregar servidor MCP personalizado", chatgpt)

        claude = " ".join(str(step.title) for step in guides["claude"].steps)
        self.assertIn("Conectores", claude)
        self.assertIn("Agregar conector personalizado", claude)

        gemini = " ".join(str(step.title) for step in guides["gemini"].steps)
        self.assertIn("Inteligencia Personalizada", gemini)
        self.assertIn("Personalizado", gemini)
