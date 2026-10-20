import sentry_sdk
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *
from config.settings.tools.django_constance import *
from config.settings.tools.django_easy_audit import *

# Fail fast on a placeholder host. The base settings default ``ALLOWED_HOSTS``
# to ``.midominio.com,localhost`` so a local run works out of the box; shipping
# that default to production would accept requests for a domain the operator
# does not own (and reject the real one). Require an explicit value.
if not ALLOWED_HOSTS or any("midominio.com" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS still contains the '.midominio.com' placeholder (or is "
        "empty); set it to the real platform domain before deploying. See "
        "docs/despliegue-multi-tenant.md."
    )

# Email settings
# https://docs.djangoproject.com/en/5.0/topics/email/

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="sandbox.smtp.mailtrap.io")
EMAIL_PORT = config("EMAIL_PORT", default="587")
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")

# Logging settings
# https://docs.djangoproject.com/en/5.0/topics/logging/

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "debug.log",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django_mcpz.calls": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# File upload settings

FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Reverse proxy and TLS
#
# The application does not terminate TLS: a reverse proxy (nginx, Caddy,
# Traefik) does, and it must forward the original scheme and host. Without
# SECURE_PROXY_SSL_HEADER Django believes every request is HTTP, so the absolute
# URLs it builds (password reset links, allauth emails) would use ``http://`` and
# the CSRF origin check would compare against the wrong scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Configuración de CSRF

CSRF_USE_SESSIONS = True
CSRF_COOKIE_HTTPONLY = True


# Origins Django accepts unsafe requests from. When the setting is empty they
# are derived from ``ALLOWED_HOSTS`` as ``https`` origins, expanding Django's
# leading-dot subdomain wildcard (``.midominio.com`` -> ``https://*.midominio.com``).
# The previous ``http://<host>`` derivation was wrong twice over: it used the
# wrong scheme for a TLS deployment and turned the wildcard into the invalid
# origin ``http://.midominio.com``.
def _trusted_origins(hosts: list[str]) -> list[str]:
    """Return ``https`` origins for the given allowed hosts.

    Args:
        hosts: Values from ``ALLOWED_HOSTS`` (a leading dot means "subdomains").

    Returns:
        Trusted origins, skipping the ``*`` catch-all which cannot be expressed
        as an origin.
    """
    origins: list[str] = []
    for host in hosts:
        host = host.strip()
        if not host or host == "*":
            continue
        if host.startswith("."):
            origins.append(f"https://*{host}")
            origins.append(f"https://{host[1:]}")
        else:
            origins.append(f"https://{host}")
    return origins


CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS", default="", cast=Csv()
) or _trusted_origins(ALLOWED_HOSTS)

# Cookies must only travel over TLS once the proxy is in place. Both default to
# ``True``; set them to ``False`` only for a deliberate HTTP-only deployment.
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)

# Never share the session or CSRF cookie across tenants. ``sessions``, ``auth``
# and ``admin`` are TENANT_APPS, so each schema owns its own ``django_session``
# table: a cookie scoped to the parent domain would be meaningless in another
# tenant's schema, and a colliding session key would read the wrong tenant's
# session. Leaving both unset is what makes cookies host-only (per subdomain).
if config("SESSION_COOKIE_DOMAIN", default="") or config(
    "CSRF_COOKIE_DOMAIN", default=""
):
    raise ImproperlyConfigured(
        "SESSION_COOKIE_DOMAIN/CSRF_COOKIE_DOMAIN must not be set: sessions live "
        "in each tenant's schema, so a cookie shared across subdomains would "
        "break tenant isolation. Remove it from the environment. See "
        "docs/despliegue-multi-tenant.md."
    )

# Configuración de seguridad para producción

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Configuración de seguridad adicional

X_FRAME_OPTIONS = "DENY"

# Sentry

sentry_sdk.init(
    dsn=config("SENTRY_DSN", default=""),
    traces_sample_rate=1.0,
    _experiments={
        "continuous_profiling_auto_start": True,
    },
)

# Celery tasks configuration

CELERY_BEAT_SCHEDULE = {
    "execute_test_task": {
        "task": "apps.core.tasks.test_task",
        "schedule": crontab(hour=22, minute=0),
        "kwargs": {},
    },
}

MIDDLEWARE += [
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# WhiteNoise settings

WHITENOISE_USE_FINDERS = True
WHITENOISE_MAX_AGE = 31536000

# Django Constance settings

CONSTANCE_BACKEND = "constance.backends.redisd.RedisBackend"

CONSTANCE_REDIS_CONNECTION = config("REDIS_URL", default="redis://127.0.0.1:6379/")

TAILWIND_DEV_MODE = False
