from config.settings.base import *
from config.settings.tools.django_constance import *
from config.settings.tools.django_easy_audit import *

# Apps settings

INSTALLED_APPS += [
    "debug_toolbar",
    "django_browser_reload",
]

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

INTERNAL_IPS = ["localhost", "127.0.0.1"]

# The dev server never terminates TLS, but tunnels such as ngrok do and forward
# ``X-Forwarded-Proto: https``. Without this header Django believes every request
# is HTTP: the MCP OAuth discovery would advertise ``http://`` issuers (hosted
# assistants reject them) and the CSRF origin check would compare against the
# wrong scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The same tunnels rewrite ``Host`` to whatever ``--host-header`` names (ngrok is
# typically started with ``--host-header=<tenant>.localhost`` so the tenant
# resolves) and carry the public name in ``X-Forwarded-Host``. Without this,
# ``request.get_host()`` stays that internal name and ``django_mcpz`` advertises
# ``https://<tenant>.localhost/...`` in the OAuth discovery documents, which a
# hosted assistant cannot reach. The tunnel's public host must also exist as a
# ``Domain`` row for the tenant, so the request still resolves to it.
USE_X_FORWARDED_HOST = True

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.cache.CachePanel",
]

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: False,
    "IS_RUNNING_TESTS": False,
}

DEBUG_TOOLBAR_CONFIG["IS_RUNNING_TESTS"] = False

# Email settings (configurable to support Mailpit in Docker)
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default="1025")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")

TAILWIND_DEV_MODE = True
