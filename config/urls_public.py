"""Root urlconf for requests served on the ``public`` schema.

Only ``SHARED_APPS`` are migrated into ``public``, so there is no session, no
auth and no admin there: this module must only reference views that never touch
a tenant-only table. It answers the platform's landing page; every client is
served from its own subdomain by :mod:`config.urls`.
"""

from __future__ import annotations

from django.urls import path
from django.views.generic import TemplateView

app_name = "public"

urlpatterns = [
    path(
        "",
        TemplateView.as_view(template_name="public/landing.html"),
        name="landing",
    ),
]
