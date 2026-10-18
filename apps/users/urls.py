from django.urls import path

from apps.users import api, views

app_name = "apps.users"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("settings/", views.SettingsView.as_view(), name="settings"),
    # Users URLs
    path("", views.UserListView.as_view(), name="user_list"),
    path("create/", views.UserCreateView.as_view(), name="user_create"),
    path(
        "<int:pk>/update/",
        views.UserUpdateView.as_view(),
        name="user_update",
    ),
    path(
        "<int:pk>/delete/",
        views.UserDeleteView.as_view(),
        name="user_delete",
    ),
    # Roles URLs
    path("roles/", views.RoleListView.as_view(), name="role_list"),
    path("roles/create/", views.RoleCreateView.as_view(), name="role_create"),
    path(
        "roles/<int:pk>/update/",
        views.RoleUpdateView.as_view(),
        name="role_update",
    ),
    path(
        "roles/<int:pk>/delete/",
        views.RoleDeleteView.as_view(),
        name="role_delete",
    ),
    # API URLs
    path(
        "api/toggle-user-status/",
        api.ToggleUserStatusView.as_view(),
        name="toggle_user_status_api",
    ),
]
