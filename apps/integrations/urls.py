"""URL routing for the integrations app."""

from django.urls import path

from apps.integrations import views

app_name = "apps.integrations"

urlpatterns = [
    path("mcp/", views.ConnectedAppsView.as_view(), name="connected_apps"),
    path(
        "mcp/<int:pk>/disconnect/",
        views.DisconnectAppView.as_view(),
        name="disconnect_app",
    ),
]
