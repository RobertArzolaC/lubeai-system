from pathlib import Path

from decouple import Csv, config
from dj_database_url import parse as db_url
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DOTENV_PATH = BASE_DIR / ".env"

load_dotenv(DOTENV_PATH)

# SECURITY WARNING: keep the secret key used in production secret!
DEBUG = config("DEBUG", default=True, cast=bool)

SECRET_KEY = config("SECRET_KEY", default="secret-key")

# Each client is served from its own subdomain: the leading dot is Django's
# subdomain wildcard. Override ``ALLOWED_HOSTS`` with the real platform domain.
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default=".midominio.com,localhost", cast=Csv())

# Application definition
#
# The platform isolates clients with one PostgreSQL schema each. ``SHARED_APPS``
# are migrated into the ``public`` schema (the tenant registry and reference
# data); ``TENANT_APPS`` are migrated into every tenant schema. A tenant
# connection searches ``<tenant>, public``, so a TENANT app may reference a
# SHARED model but never the opposite: a SHARED model must not have a foreign
# key to a TENANT model (see ``apps.tenancy.models.Tenant``, which deliberately
# drops the project's ``created_by``/``updated_by`` mixin). An app listed in
# both is installed in public and in every tenant schema.

SHARED_APPS = [
    "django_tenants",
    "apps.tenancy",
    "django.contrib.contenttypes",
    "cities_light",
    "constance",
    "constance.backends.database",
    # tenant-schemas-celery merges the periodic tasks of the public schema and
    # of every tenant schema, so django-celery-beat needs its tables in both.
    "django_celery_beat",
]

TENANT_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "allauth",
    "allauth.account",
    "easyaudit",
    "widget_tweaks",
    "django_filters",
    "django_extensions",
    "rest_framework",
    "rest_framework.authtoken",
    "django_celery_beat",
    "sesame",
    "dal",
    "dal_select2",
    "tailwind",
    "apps.core",
    "apps.authentication",
    "apps.users",
    "apps.theme",
    "apps.organizations",
    "apps.equipment",
    "apps.reports",
    "apps.alerts",
    "apps.dashboard",
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TAILWIND_APP_NAME = "apps.theme"
TAILWIND_USE_STANDALONE_BINARY = True
TAILWIND_STANDALONE_BINARY_VERSION = "v4.2.2"
TAILWIND_STANDALONE_START_COMMAND_ARGS = (
    "-i static_src/src/styles.css -o static/css/dist/styles.css --watch=always"
)


INTERNAL_IPS = [
    "127.0.0.1",
]

MIDDLEWARE = [
    # Must stay first: it selects the tenant schema (and the urlconf) from the
    # request host before any other middleware reads or writes the database.
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "easyaudit.middleware.easyaudit.EasyAuditMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "constance.context_processors.config",
                "apps.core.context_processors.site_processor",
                "apps.organizations.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
#
# PostgreSQL is mandatory in every environment (development and tests included):
# the tenant backend below swaps the search path per request and has no SQLite
# support, so there is deliberately no SQLite fallback. ``DATABASE_URL`` is
# provided by docker compose in the containers.

DATABASE_URL = config("DATABASE_URL", default="")

if not DATABASE_URL.startswith(("postgres://", "postgresql://", "psql://")):
    raise ImproperlyConfigured(
        "DATABASE_URL must point to a PostgreSQL database; SQLite is not "
        "supported by the schema-per-tenant backend."
    )

DATABASES = {"default": db_url(DATABASE_URL)}
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"

# Routes every migration to the right schema: SHARED_APPS to ``public`` and
# TENANT_APPS to the tenant schema being migrated.
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "es-pe"

TIME_ZONE = "America/Lima"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Translation settings
# https://docs.djangoproject.com/en/5.0/topics/i18n/translation/

LANGUAGES = (
    ("es", _("Spanish")),
    # ("en", _("English")),
)

LOCALE_PATHS = [BASE_DIR / "locale/"]

# Django Cities Light settings
# https://github.com/yourlabs/django-cities-light

CITIES_LIGHT_TRANSLATION_LANGUAGES = ["es", "en"]
CITIES_LIGHT_INCLUDE_COUNTRIES = ["PE"]

# Tenancy settings
# https://django-tenants.readthedocs.io/en/latest/install.html
#
# The tenant registry and its domains live in the ``public`` schema and replace
# the former subdomain/``DEFAULT_TENANT_SLUG`` resolution. A host that matches
# no ``Domain`` must answer 404, so ``SHOW_PUBLIC_IF_NO_TENANT_FOUND`` stays off
# and there is no fallback tenant. ``PUBLIC_SCHEMA_URLCONF`` is the public
# landing page, which has no session and no admin.

TENANT_MODEL = "tenancy.Tenant"
TENANT_DOMAIN_MODEL = "tenancy.Domain"

PUBLIC_SCHEMA_URLCONF = "config.urls_public"

# Skip redundant ``SET search_path`` statements when the path is already right.
TENANT_LIMIT_SET_CALLS = True

# Django Allauth settings
# https://django-allauth.readthedocs.io/en/latest/configuration.html

AUTH_USER_MODEL = "users.User"

SITE_ID = 1

LOGIN_URL = "/"

LOGIN_REDIRECT_URL = "/dashboard/"

ACCOUNT_SIGNUP_REDIRECT_URL = "/login/"

ACCOUNT_LOGIN_METHODS = {"email"}

ACCOUNT_USER_MODEL_USERNAME_FIELD = None

ACCOUNT_LOGOUT_ON_GET = True

ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]

ACCOUNT_EMAIL_VERIFICATION = "none"

# Users are created by their organization (invite/B2B); public self-signup is
# disabled so a self-registered account cannot end up without a tenant.
ACCOUNT_ALLOW_REGISTRATION = False

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_FORMS = {"signup": "apps.authentication.forms.CustomSignupForm"}


# Django Rest Framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
}

# Celery settings

CELERY_TIMEZONE = TIME_ZONE
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"
CELERY_BROKER_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://127.0.0.1:6379/")

# Cache settings
#
# Use a shared cache (Redis) when ``CACHE_URL`` is set so all workers share the
# same entries. Fall back to a local-memory cache for host runs and tests.
CACHE_URL = config("CACHE_URL", default="")

if CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "lubeai-default",
        }
    }
