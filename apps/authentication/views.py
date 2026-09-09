from allauth.account import views as allauth_views
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import ValidationError
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.authentication import forms, services


@method_decorator(csrf_exempt, name="dispatch")
class ChangePasswordView(View):
    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user, request.POST)
        response = {"status": "error", "errors": {}}

        if not form.is_valid():
            return JsonResponse(response, status=400)

        user = form.save()
        update_session_auth_hash(request, user)
        return JsonResponse(
            {"status": "success", "message": "Password changed successfully."}
        )


@method_decorator(csrf_exempt, name="dispatch")
class DeactivateAccountView(View):
    def post(self, request, *args, **kwargs):
        form = forms.DeactivateAccountForm(request.POST)
        response = {"status": "error", "errors": {}}

        if not form.is_valid():
            return JsonResponse(response, status=400)

        try:
            user = form.save()
        except ValidationError:
            return JsonResponse(response, status=400)

        user.is_active = False
        user.save()
        return JsonResponse(
            {"status": "success", "message": "Account deactivated successfully."}
        )


class ValidatePasswordView(LoginRequiredMixin, View):
    """Validates a candidate password against the configured validators."""

    def post(self, request, *args, **kwargs):
        password = request.POST.get("password") or ""
        checks = services.get_password_checks(password, user=request.user)
        return JsonResponse({"checks": checks})


class PasswordChangeView(allauth_views.PasswordChangeView):
    """Renders the dashboard-styled password change page."""

    success_url = reverse_lazy("apps.users:settings")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["password_checks"] = services.get_password_checks(
            None, user=self.request.user
        )
        context["back_url"] = reverse_lazy("apps.users:settings")
        return context
