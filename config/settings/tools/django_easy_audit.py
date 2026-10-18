# Django easy audit settings
# https://github.com/soynatan/django-easy-audit

DJANGO_EASY_AUDIT_WATCH_AUTH_EVENTS = True
DJANGO_EASY_AUDIT_WATCH_MODEL_EVENTS = True
DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS = True

# The tenant registry lives in the ``public`` schema while ``easyaudit`` is a
# TENANT app: auditing a Tenant or Domain save would try to write a CRUD event
# into a table that does not exist in public. The registry is platform
# infrastructure, not client business data, so it is not audited.
DJANGO_EASY_AUDIT_UNREGISTERED_CLASSES_EXTRA = [
    "tenancy.Tenant",
    "tenancy.Domain",
]
