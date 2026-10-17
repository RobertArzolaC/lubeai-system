from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.users import models


class ToggleUserStatusView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        user_id = request.POST.get("user_id")
        action = request.POST.get("action")

        try:
            user = models.User.objects.get(pk=int(user_id))
        except (TypeError, ValueError, models.User.DoesNotExist):
            return JsonResponse(
                {"success": False, "message": _("User not found")},
                status=404,
            )

        if action == "activate":
            user.is_active = True
        elif action == "deactivate":
            user.is_active = False
        else:
            return JsonResponse({"success": False, "message": _("Invalid action")})

        user.save()

        return JsonResponse(
            {
                "success": True,
                "message": _("User status has been successfully updated"),
                "is_active": user.is_active,
            }
        )
