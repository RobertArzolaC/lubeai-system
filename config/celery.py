import os
from pathlib import Path

from django.conf import settings
from dotenv import load_dotenv
from tenant_schemas_celery.app import CeleryApp

BASE_DIR = Path(__file__).resolve().parent.parent
DOTENV_PATH = BASE_DIR / ".env"
load_dotenv(DOTENV_PATH)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# The business apps (alerts included) are tenant-scoped, so a worker that starts
# on ``public`` cannot run their tasks. ``tenant_schemas_celery`` makes the app
# tenant-aware: it records the schema of the dispatching context in the task
# headers and re-activates it inside the worker before the task body runs.
app = CeleryApp("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.broker_connection_retry_on_startup = True
app.conf.update(
    BROKER_URL=settings.CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND=settings.CELERY_RESULT_BACKEND,
)
app.autodiscover_tasks()
