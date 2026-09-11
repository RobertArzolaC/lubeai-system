"""Tests for the ``apps.equipment.autocomplete`` endpoints."""

import json

from django.test import TestCase
from django.urls import reverse

from apps.equipment import factories


def forward_payload(**values: object) -> str:
    """Build the JSON ``forward`` payload DAL sends from the widget."""
    return json.dumps(values)


class MachineAutocompleteTests(TestCase):
    """Tests for :class:`autocomplete.MachineAutocomplete`."""

    def setUp(self) -> None:
        self.machine = factories.MachineFactory(name="Alpha Vessel")
        self.other = factories.MachineFactory(name="Beta Vessel")
        self.url = reverse("apps.equipment:autocomplete_machine")

    def test_lists_active_machines(self) -> None:
        """Both active machines are returned."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ids = {int(item["id"]) for item in response.json()["results"]}
        self.assertEqual(ids, {self.machine.pk, self.other.pk})

    def test_excludes_inactive_machines(self) -> None:
        """Inactive machines are not returned."""
        inactive = factories.MachineFactory(name="Inactive", is_active=False)
        response = self.client.get(self.url)
        ids = {int(item["id"]) for item in response.json()["results"]}
        self.assertNotIn(inactive.pk, ids)

    def test_filters_by_term(self) -> None:
        """The ``q`` term narrows the results by name."""
        response = self.client.get(self.url, {"q": "Alpha"})
        ids = {int(item["id"]) for item in response.json()["results"]}
        self.assertEqual(ids, {self.machine.pk})


class ComponentAutocompleteTests(TestCase):
    """Tests for :class:`autocomplete.ComponentAutocomplete`."""

    def setUp(self) -> None:
        self.machine = factories.MachineFactory()
        self.other_machine = factories.MachineFactory()
        self.component = factories.ComponentFactory(machine=self.machine)
        self.other_component = factories.ComponentFactory(machine=self.other_machine)
        self.url = reverse("apps.equipment:autocomplete_component")

    def test_returns_only_components_of_machine(self) -> None:
        """Only components of the forwarded machine are returned."""
        response = self.client.get(
            self.url, {"forward": forward_payload(machine=self.machine.pk)}
        )
        self.assertEqual(response.status_code, 200)
        ids = {int(item["id"]) for item in response.json()["results"]}
        self.assertEqual(ids, {self.component.pk})

    def test_empty_without_machine(self) -> None:
        """Without a forwarded machine the result set is empty."""
        response = self.client.get(self.url)
        self.assertEqual(response.json()["results"], [])

    def test_excludes_inactive_components(self) -> None:
        """Inactive components are not returned."""
        inactive = factories.ComponentFactory(machine=self.machine, is_active=False)
        response = self.client.get(
            self.url, {"forward": forward_payload(machine=self.machine.pk)}
        )
        ids = {int(item["id"]) for item in response.json()["results"]}
        self.assertNotIn(inactive.pk, ids)

    def test_filters_by_type_name(self) -> None:
        """The ``q`` term narrows the results by component type name."""
        component_type = factories.ComponentTypeFactory(name="Alpha Pump")
        match = factories.ComponentFactory(machine=self.machine, type=component_type)
        response = self.client.get(
            self.url,
            {"forward": forward_payload(machine=self.machine.pk), "q": "Alpha"},
        )
        ids = {int(item["id"]) for item in response.json()["results"]}
        self.assertEqual(ids, {match.pk})
