from django.urls import path

from apps.core import autocomplete

app_name = "apps.core"

urlpatterns = [
    path(
        "autocomplete/country/",
        autocomplete.CountryAutocomplete.as_view(),
        name="autocomplete_country",
    ),
    path(
        "autocomplete/region/",
        autocomplete.RegionAutocomplete.as_view(),
        name="autocomplete_region",
    ),
    path(
        "autocomplete/subregion/",
        autocomplete.SubRegionAutocomplete.as_view(),
        name="autocomplete_subregion",
    ),
    path(
        "autocomplete/city/",
        autocomplete.CityAutocomplete.as_view(),
        name="autocomplete_city",
    ),
]
