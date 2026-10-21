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

    def test_provider_step_order_is_exact(self) -> None:
        """Each provider keeps the menu order documented for its UI."""
        guides = {guide.slug: guide for guide in provider_guides(MCP_URL)}

        self.assertEqual(
            [str(step.title) for step in guides["chatgpt"].steps],
            [
                "Abre Complementos",
                "Agregar servidor MCP personalizado",
                "Completa el formulario",
                "Crea el complemento",
            ],
        )
        self.assertEqual(
            [str(step.title) for step in guides["claude"].steps],
            [
                "Abre Configuración",
                "Entra a Conectores",
                "Pulsa Agregar +",
                "Elige Agregar conector personalizado",
                "Autoriza el acceso",
            ],
        )
        self.assertEqual(
            [str(step.title) for step in guides["gemini"].steps],
            [
                "Abre Ajustes",
                "Entra a Inteligencia Personalizada",
                "Pulsa Personalizado +",
                "Autoriza el acceso",
            ],
        )

    def test_gemini_guide_states_its_restrictions(self) -> None:
        """Gemini's account, region, language and activity limits are listed."""
        guide = next(
            item for item in provider_guides(MCP_URL) if item.slug == "gemini"
        )
        notes = " ".join(str(note) for note in guide.notes)
        for text in (
            "cuenta personal",
            "18 años",
            "Estados Unidos",
            "inglés",
            "Keep Activity",
        ):
            self.assertIn(text, notes)
        self.assertIn("Conexión solo por web", str(guide.availability))
