from django import template
from django.urls import resolve, reverse
from django.urls.exceptions import Resolver404
from django.utils.translation import gettext_lazy as _

from apps.core.breadcrumbs import resolve_breadcrumb_label

register = template.Library()


@register.simple_tag(takes_context=True)
def breadcrumb(context):
    """Build the breadcrumb trail for the current request.

    Args:
        context: The template context (must contain ``request``).

    Returns:
        A list of breadcrumb dicts with ``title``, ``url`` and ``is_active``.
    """
    request = context["request"]
    dashboard_url = reverse("apps.dashboard:index")

    breadcrumbs = [
        {
            "title": _("Dashboard"),
            "url": dashboard_url,
            "is_active": request.path == dashboard_url,
        }
    ]

    current_path = "/"

    for part in (segment for segment in request.path.split("/") if segment):
        current_path += f"{part}/"

        # The dashboard root is already the first crumb.
        if current_path == dashboard_url:
            continue

        try:
            url_name = resolve(current_path).url_name
        except Resolver404:
            continue

        title = resolve_breadcrumb_label(url_name)
        if title is None:
            continue

        breadcrumbs.append(
            {
                "title": title,
                "url": current_path,
                "is_active": current_path == request.path,
            }
        )

    return breadcrumbs
