from django.urls import path

from apps.equipment import autocomplete, views

app_name = "apps.equipment"

urlpatterns = [
    # Autocomplete URLs
    path(
        "machines/autocomplete/",
        autocomplete.MachineAutocomplete.as_view(),
        name="autocomplete_machine",
    ),
    path(
        "components/autocomplete/",
        autocomplete.ComponentAutocomplete.as_view(),
        name="autocomplete_component",
    ),
    # Machine URLs
    path("machines/", views.MachineListView.as_view(), name="machine_list"),
    path(
        "machines/create/",
        views.MachineCreateView.as_view(),
        name="machine_create",
    ),
    path(
        "machines/<int:pk>/",
        views.MachineDetailView.as_view(),
        name="machine_detail",
    ),
    path(
        "machines/<int:pk>/update/",
        views.MachineUpdateView.as_view(),
        name="machine_update",
    ),
    path(
        "machines/<int:pk>/delete/",
        views.MachineDeleteView.as_view(),
        name="machine_delete",
    ),
    # Branch URLs
    path("branches/", views.BranchListView.as_view(), name="branch_list"),
    path("branches/create/", views.BranchCreateView.as_view(), name="branch_create"),
    path(
        "branches/<int:pk>/",
        views.BranchDetailView.as_view(),
        name="branch_detail",
    ),
    path(
        "branches/<int:pk>/update/",
        views.BranchUpdateView.as_view(),
        name="branch_update",
    ),
    path(
        "branches/<int:pk>/delete/",
        views.BranchDeleteView.as_view(),
        name="branch_delete",
    ),
    # Fleet URLs
    path("fleets/", views.FleetListView.as_view(), name="fleet_list"),
    path("fleets/create/", views.FleetCreateView.as_view(), name="fleet_create"),
    path(
        "fleets/<int:pk>/",
        views.FleetDetailView.as_view(),
        name="fleet_detail",
    ),
    path(
        "fleets/<int:pk>/update/",
        views.FleetUpdateView.as_view(),
        name="fleet_update",
    ),
    path(
        "fleets/<int:pk>/delete/",
        views.FleetDeleteView.as_view(),
        name="fleet_delete",
    ),
    # Component Type URLs
    path(
        "component-types/",
        views.ComponentTypeListView.as_view(),
        name="component_type_list",
    ),
    path(
        "component-types/create/",
        views.ComponentTypeCreateView.as_view(),
        name="component_type_create",
    ),
    path(
        "component-types/<int:pk>/",
        views.ComponentTypeDetailView.as_view(),
        name="component_type_detail",
    ),
    path(
        "component-types/<int:pk>/update/",
        views.ComponentTypeUpdateView.as_view(),
        name="component_type_update",
    ),
    path(
        "component-types/<int:pk>/delete/",
        views.ComponentTypeDeleteView.as_view(),
        name="component_type_delete",
    ),
]
