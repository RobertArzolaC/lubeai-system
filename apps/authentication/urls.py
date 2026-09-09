from django.urls import path

from apps.authentication import views

app_name = "apps.authentication"

urlpatterns = [
    path(
        "api/change-password/",
        views.ChangePasswordView.as_view(),
        name="api_change_password",
    ),
    path(
        "api/deactivate-account/",
        views.DeactivateAccountView.as_view(),
        name="api_deactivate_account",
    ),
    path(
        "api/validate-password/",
        views.ValidatePasswordView.as_view(),
        name="validate_password_api",
    ),
]
