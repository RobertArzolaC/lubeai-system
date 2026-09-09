from django.views.generic import TemplateView


class BaseErrorView(TemplateView):
    """Render an error template honoring its HTTP status on any method."""

    status_code = 500

    def dispatch(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        response = self.render_to_response(context)
        response.status_code = self.status_code
        return response


class Error404View(BaseErrorView):
    template_name = "errors/404.html"
    status_code = 404


class Error500View(BaseErrorView):
    template_name = "errors/500.html"
    status_code = 500


class Error403View(BaseErrorView):
    template_name = "errors/403.html"
    status_code = 403
