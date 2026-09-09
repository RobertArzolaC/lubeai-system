"""Tests for the ``apps.core.mixins.views`` module."""

import json

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core import mixins as core_mixins
from apps.users import models as users_models
from apps.users.factories import AccountFactory, UserFactory


class DeleteTestView(core_mixins.BaseDeleteView):
    """Minimal delete view bound to the Account model."""

    model = users_models.Account
    permission_required = "users.delete_account"


def parse_json(response) -> dict:
    """Decode a plain :class:`django.http.JsonResponse` body."""
    return json.loads(response.content)


class BaseDeleteViewTests(TestCase):
    """Tests for :class:`BaseDeleteView` behavior."""

    def setUp(self) -> None:
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.factory = RequestFactory()

    def post_request(self, pk: int):
        """Build an authenticated POST request for the given pk."""
        request = self.factory.post(
            reverse("apps.users:account_delete", kwargs={"pk": pk})
        )
        request.user = self.user
        view = DeleteTestView()
        view.request = request
        view.kwargs = {"pk": pk}
        return request, view

    def test_delete_success_returns_json(self) -> None:
        """Deleting an existing object returns a JSON success response."""
        account = AccountFactory()
        request, view = self.post_request(account.pk)
        response = view.post(request, pk=account.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse_json(response)["status"], "success")
        account.refresh_from_db()
        self.assertTrue(account.is_removed)

    def test_delete_missing_object_returns_404(self) -> None:
        """Deleting a missing object returns a JSON 404 response."""
        request, view = self.post_request(999999)
        response = view.post(request, pk=999999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(parse_json(response)["status"], "error")

    def test_handle_no_permission_returns_json_403(self) -> None:
        """Permission errors are reported as JSON 403 responses."""
        _request, view = self.post_request(1)
        response = view.handle_no_permission()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(parse_json(response)["status"], "error")
