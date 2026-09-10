"""URL routing for the alerts app."""

from django.urls import path

from apps.alerts import views

app_name = "apps.alerts"

urlpatterns = [
    path("", views.AlertListView.as_view(), name="alert_list"),
    path("<int:pk>/", views.AlertDetailView.as_view(), name="alert_detail"),
    path(
        "<int:pk>/update/",
        views.AlertUpdateView.as_view(),
        name="alert_update",
    ),
    path(
        "<int:pk>/delete/",
        views.AlertDeleteView.as_view(),
        name="alert_delete",
    ),
]
