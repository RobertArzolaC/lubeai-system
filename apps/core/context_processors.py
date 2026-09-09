from django.contrib.sites.shortcuts import get_current_site


def site_processor(request):
    """
    Context processor to add the current Site object to the template context.
    Provides `{{ site }}` universally across all templates.
    """
    return {"site": get_current_site(request)}
