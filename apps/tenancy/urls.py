"""URL routing for the platform's tenant console.

Registered in the tenant urlconf (``config.urls``), not in a SHARED one: the
console needs ``auth`` and ``sessions``, which only exist inside a tenant
schema. The views themselves restrict access to the operations tenant.
"""

from django.urls import path

from apps.tenancy import views

app_name = "apps.tenancy"

urlpatterns = [
    path("", views.TenantListView.as_view(), name="tenant_list"),
    path("create/", views.TenantCreateView.as_view(), name="tenant_create"),
    path("<int:pk>/", views.TenantDetailView.as_view(), name="tenant_detail"),
    path(
        "<int:pk>/update/",
        views.TenantUpdateView.as_view(),
        name="tenant_update",
    ),
    path(
        "<int:pk>/toggle-active/",
        views.TenantToggleActiveView.as_view(),
        name="tenant_toggle_active",
    ),
]
