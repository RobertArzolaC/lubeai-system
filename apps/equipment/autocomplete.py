"""Django Autocomplete Light endpoints for equipment models."""

from dal import autocomplete
from django.db.models import Q, QuerySet

from apps.equipment import models


class MachineAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete endpoint for machines filtered by the requested term."""

    def get_queryset(self) -> QuerySet:
        """Return active machines filtered by the requested term."""
        queryset = models.Machine.objects.filter(is_active=True)
        if self.q:
            queryset = queryset.filter(
                Q(name__icontains=self.q) | Q(serial_number__icontains=self.q)
            )
        return queryset.order_by("name")


class ComponentAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete endpoint for components scoped to a machine."""

    def get_queryset(self) -> QuerySet:
        """Return active components of the forwarded machine, filtered by term."""
        queryset = models.Component.objects.filter(is_active=True).select_related(
            "type", "machine"
        )

        machine = self.forwarded.get("machine")
        if not machine:
            return queryset.none()

        queryset = queryset.filter(machine_id=machine)
        if self.q:
            queryset = queryset.filter(
                Q(type__name__icontains=self.q) | Q(machine__name__icontains=self.q)
            )
        return queryset.order_by("type__name")

    def get_result_label(self, result: models.Component) -> str:
        """Return the label shown for a component result."""
        return str(result)
