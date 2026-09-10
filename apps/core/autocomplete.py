"""Django Autocomplete Light endpoints for ``cities_light`` location fields."""

from cities_light.models import City, Country, Region, SubRegion
from dal import autocomplete
from django.db.models import QuerySet


class CountryAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete endpoint for countries."""

    def get_queryset(self) -> QuerySet:
        """Return countries filtered by the requested term."""
        queryset = Country.objects.all()
        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        return queryset.order_by("name")


class RegionAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete endpoint for regions, optionally scoped to a country."""

    def get_queryset(self) -> QuerySet:
        """Return regions filtered by the forwarded country and term."""
        queryset = Region.objects.all()
        country = self.forwarded.get("country")
        if country:
            queryset = queryset.filter(country_id=country)
        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        return queryset.order_by("name")


class SubRegionAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete endpoint for subregions scoped to country and region."""

    def get_queryset(self) -> QuerySet:
        """Return subregions filtered by the forwarded country, region and term."""
        queryset = SubRegion.objects.all()
        country = self.forwarded.get("country")
        region = self.forwarded.get("region")
        if country:
            queryset = queryset.filter(country_id=country)
        if region:
            queryset = queryset.filter(region_id=region)
        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        return queryset.order_by("name")


class CityAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete endpoint for cities scoped to country, region and subregion."""

    def get_queryset(self) -> QuerySet:
        """Return cities filtered by the forwarded location fields and term."""
        queryset = City.objects.all()
        country = self.forwarded.get("country")
        region = self.forwarded.get("region")
        subregion = self.forwarded.get("subregion")
        if country:
            queryset = queryset.filter(country_id=country)
        if region:
            queryset = queryset.filter(region_id=region)
        if subregion:
            queryset = queryset.filter(subregion_id=subregion)
        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        return queryset.order_by("name")
