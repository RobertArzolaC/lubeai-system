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


class ListTestView(core_mixins.BaseListView):
    """Minimal list view bound to the Account model."""

    model = users_models.Account
    permission_required = "users.view_account"
    template_name = "users/account/list.html"


class CustomPageSizeListView(ListTestView):
    """List view overriding the default page size."""

    paginate_by = 50


def parse_json(response) -> dict:
    """Decode a plain :class:`django.http.JsonResponse` body."""
    return json.loads(response.content)


class BaseListViewPaginationTests(TestCase):
    """Tests for the pagination behavior of :class:`BaseListView`."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def build_view(self, view_class, query: str = ""):
        """Build a list view bound to a GET request with ``query``."""
        request = self.factory.get(f"/?{query}" if query else "/")
        request.user = UserFactory(is_staff=True, is_superuser=True)
        view = view_class()
        view.request = request
        view.kwargs = {}
        return view

    def test_default_page_size_is_5(self) -> None:
        """Without parameters the default page size is 5."""
        view = self.build_view(ListTestView)
        self.assertEqual(view.get_paginate_by(users_models.Account.objects.all()), 5)

    def test_items_per_page_param_is_used(self) -> None:
        """A valid ``items_per_page`` parameter overrides the default."""
        view = self.build_view(ListTestView, "items_per_page=10")
        self.assertEqual(view.get_paginate_by(users_models.Account.objects.all()), 10)

    def test_invalid_items_per_page_falls_back(self) -> None:
        """An out-of-range ``items_per_page`` falls back to the default."""
        view = self.build_view(ListTestView, "items_per_page=999")
        self.assertEqual(view.get_paginate_by(users_models.Account.objects.all()), 5)

    def test_non_numeric_items_per_page_falls_back(self) -> None:
        """A non-numeric ``items_per_page`` falls back to the default."""
        view = self.build_view(ListTestView, "items_per_page=abc")
        self.assertEqual(view.get_paginate_by(users_models.Account.objects.all()), 5)

    def test_subclass_default_is_respected(self) -> None:
        """A subclass ``paginate_by`` value is used when no param is given."""
        view = self.build_view(CustomPageSizeListView)
        self.assertEqual(view.get_paginate_by(users_models.Account.objects.all()), 50)

    def test_param_overrides_subclass_default(self) -> None:
        """The ``items_per_page`` parameter overrides a subclass default."""
        view = self.build_view(CustomPageSizeListView, "items_per_page=5")
        self.assertEqual(view.get_paginate_by(users_models.Account.objects.all()), 5)


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
