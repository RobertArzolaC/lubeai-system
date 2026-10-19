"""Free-text search shared by the dashboard filter and its service.

The dashboard's search box narrows both the sample dataset and the alert
aggregates, so the lookup fields live in one place: the ``FilterSet`` validates
the request and the service applies the same predicate when it builds the
payload, which keeps the JSON endpoint and the initial page render consistent.
"""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import Final

from django.db.models import Q

#: ``Report`` lookups the dashboard search matches: the report identifiers, its
#: machine and its component type.
REPORT_SEARCH_FIELDS: Final[tuple[str, ...]] = (
    "lab_number",
    "per_number",
    "serial_number_code",
    "machine__name",
    "component__type__name",
)

#: ``Alert`` lookups the dashboard search matches. Alerts carry the machine and
#: the source report, so the report identifiers are reachable through it.
ALERT_SEARCH_FIELDS: Final[tuple[str, ...]] = (
    "machine__name",
    "component__type__name",
    "report__lab_number",
    "report__per_number",
    "report__serial_number_code",
)


def build_search_q(fields: tuple[str, ...], value: str) -> Q:
    """Return a case-insensitive ``OR`` of ``contains`` lookups.

    Args:
        fields: Model lookups to match, e.g. ``("machine__name",)``.
        value: Text typed in the dashboard's search box.

    Returns:
        A single ``Q`` object combining every field with ``OR``.
    """
    return reduce(or_, (Q(**{f"{field}__icontains": value}) for field in fields))
