"""Constants for the dashboard app."""

from typing import Final

ISO4406_TARGET_VALUES: Final[tuple[int, int, int]] = (22, 20, 17)

CONDITION_COLORS: Final[dict[str, str]] = {
    "NORMAL": "#12b76a",
    "CAUTION": "#FFA70B",
    "CRITICAL": "#f04438",
}

ISO4406_STATUS_COLORS: Final[dict[str, str]] = {
    "normal": "#12b76a",
    "warning": "#FFA70B",
    "critical": "#f04438",
}

DEFAULT_CACHE_TIMEOUT: Final[int] = 60
DEFAULT_RECENT_REPORTS: Final[int] = 25
