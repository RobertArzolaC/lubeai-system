"""Tests for the ``apps.core.mixins.cache`` module."""

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path
from django.views import View

from apps.core.mixins.cache import CacheMixin
from apps.users.factories import UserFactory


class CountingCachedView(CacheMixin, View):
    """View that counts its executions to observe caching."""

    cache_timeout = 300
    counter = 0

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """Count the call and return a stable response."""
        type(self).counter += 1
        return HttpResponse("cached-response")


urlpatterns = [
    path("cached/", CountingCachedView.as_view(), name="cached"),
]


@override_settings(ROOT_URLCONF=__name__)
class CacheMixinTests(TestCase):
    """Tests for the :class:`CacheMixin`."""

    def setUp(self) -> None:
        cache.clear()
        CountingCachedView.counter = 0
        self.factory = RequestFactory()

    def test_default_cache_timeout(self) -> None:
        """The default cache timeout is 60 seconds."""
        self.assertEqual(CacheMixin().get_cache_timeout(), 60)

    def test_custom_cache_timeout(self) -> None:
        """Subclasses can customize the cache timeout."""
        self.assertEqual(CountingCachedView().get_cache_timeout(), 300)

    def test_key_prefix_for_anonymous_user(self) -> None:
        """Anonymous requests use the ``user_anonymous`` prefix."""
        request = self.factory.get("/cached/")
        request.user = AnonymousUser()
        self.assertEqual(
            CountingCachedView().get_cache_key_prefix(request),
            "user_anonymous",
        )

    def test_key_prefix_for_authenticated_user(self) -> None:
        """Authenticated requests use the user id in the prefix."""
        user = UserFactory()
        request = self.factory.get("/cached/")
        request.user = user
        self.assertEqual(
            CountingCachedView().get_cache_key_prefix(request),
            f"user_{user.id}",
        )

    def test_dispatch_caches_response(self) -> None:
        """A second identical request is served from cache."""
        response_one = self.client.get("/cached/")
        response_two = self.client.get("/cached/")
        self.assertEqual(response_one.status_code, 200)
        self.assertEqual(response_one.content, response_two.content)
        self.assertEqual(CountingCachedView.counter, 1)
