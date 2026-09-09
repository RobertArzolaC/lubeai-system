from django.views import View
from django.views.decorators.cache import cache_page


class CacheMixin(View):
    cache_timeout = 60

    def get_cache_timeout(self):
        return self.cache_timeout

    def get_cache_key_prefix(self, request):
        user_id = request.user.id if request.user.is_authenticated else "anonymous"
        return f"user_{user_id}"

    def dispatch(self, request, *args, **kwargs):
        cache_key_prefix = self.get_cache_key_prefix(request)

        view = cache_page(
            timeout=self.get_cache_timeout(),
            key_prefix=cache_key_prefix,
        )(super().dispatch)

        return view(request, *args, **kwargs)
