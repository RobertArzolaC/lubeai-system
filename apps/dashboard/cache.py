"""Cache helpers for the dashboard payload.

The dashboard payload is global (it does not depend on the current user), so it
is cached keyed by the applied filters. A single version counter invalidates
every combination at once when the underlying data changes.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "dashboard:payload"
CACHE_VERSION_KEY = "dashboard:version"
DEFAULT_VERSION = 1


def get_cache_version() -> int:
    """Return the current dashboard cache version."""
    return cache.get(CACHE_VERSION_KEY, DEFAULT_VERSION)


def bump_cache_version() -> int:
    """Invalidate every cached dashboard payload by bumping the version.

    Failures are logged instead of raised so a cache outage never blocks a
    database write.

    Returns:
        The new version number.
    """
    try:
        if cache.add(CACHE_VERSION_KEY, DEFAULT_VERSION + 1):
            return DEFAULT_VERSION + 1
        return cache.incr(CACHE_VERSION_KEY)
    except Exception:
        logger.warning("Could not bump the dashboard cache version", exc_info=True)
        return get_cache_version()


def build_payload_key(filters_key: str) -> str:
    """Return the cache key for a payload given a filter signature."""
    return f"{CACHE_KEY_PREFIX}:{get_cache_version()}:{filters_key}"


def safe_cache_get(key: str):
    """Return a cached value, ignoring cache backend failures."""
    try:
        return cache.get(key)
    except Exception:
        logger.warning("Dashboard cache read failed for %s", key, exc_info=True)
        return None


def safe_cache_set(key: str, value, timeout: int) -> None:
    """Store a value in the cache, ignoring cache backend failures."""
    try:
        cache.set(key, value, timeout)
    except Exception:
        logger.warning("Dashboard cache write failed for %s", key, exc_info=True)
