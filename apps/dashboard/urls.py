"""URL routing for the dashboard app."""

from django.urls import path

from apps.dashboard import views

app_name = "apps.dashboard"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="index"),
    path("data/", views.DashboardDataView.as_view(), name="data"),
]
