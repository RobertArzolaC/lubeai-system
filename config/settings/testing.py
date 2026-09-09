from config.settings.base import *
from config.settings.tools.django_constance import *
from config.settings.tools.django_easy_audit import *

# Disable easyaudit settings
DJANGO_EASY_AUDIT_WATCH_AUTH_EVENTS = False
DJANGO_EASY_AUDIT_WATCH_MODEL_EVENTS = False
DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS = False

# Static files (CSS, JavaScript, Images)
# STATIC_ROOT = BASE_DIR / "staticfiles"
# Keep DEBUG off so dev-only tooling (debug_toolbar, browser_reload) is not
# imported by config.urls and real error handlers (404/500/403) are used.
DEBUG = False

# Email settings
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Testing settings
TESTING = True
