"""Every number the Dashboard decides something with, in one place.

Settings (Module 8) will own these values and let an administrator change them. Until
then they are constants here, so a rule is never written twice and a change is one edit
in one file. Nothing in this module reads them from the database.

Severity: an alert is shown in wheat ("needs attention") unless it is listed in
:data:`CRITICAL_ALERTS`, which is the only place the error red is used on the
dashboard - a loss of traceability or a legal problem, not a backlog.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------- alert rules

#: A ready field with no pickup request is flagged after this many days (over 7 means
#: the eighth day and later).
READY_WITHOUT_PICKUP_DAYS: Final = 7

#: An open heap or batch with nothing added and no bale made for this long is idle.
HEAP_IDLE_DAYS: Final = 14

#: A draft fieldbook untouched for this long is probably forgotten.
DRAFT_FIELDBOOK_IDLE_DAYS: Final = 21

#: A hemp licence expiring within this many days is flagged; an expired one is critical.
LICENCE_EXPIRY_WARNING_DAYS: Final = 30

#: A scheduled delivery is late once its scheduled date has passed without a dispatch.
DISPATCH_GRACE_DAYS: Final = 0

ALERT_READY_WITHOUT_PICKUP: Final = "ready_without_pickup"
ALERT_OVERDUE_FIELDS: Final = "overdue_fields"
ALERT_DISPATCH_OVERDUE: Final = "dispatch_overdue"
ALERT_WEIGHT_VARIANCE: Final = "weight_variance"
ALERT_IDLE_HEAPS: Final = "idle_heaps"
ALERT_LICENCE_EXPIRY: Final = "licence_expiry"
ALERT_STALE_DRAFTS: Final = "stale_drafts"
ALERT_FARMERS_WITHOUT_FIELD: Final = "farmers_without_field"

ALERT_KEYS: Final[tuple[str, ...]] = (
    ALERT_READY_WITHOUT_PICKUP,
    ALERT_OVERDUE_FIELDS,
    ALERT_DISPATCH_OVERDUE,
    ALERT_WEIGHT_VARIANCE,
    ALERT_IDLE_HEAPS,
    ALERT_LICENCE_EXPIRY,
    ALERT_STALE_DRAFTS,
    ALERT_FARMERS_WITHOUT_FIELD,
)

SEVERITY_ATTENTION: Final = "attention"
SEVERITY_CRITICAL: Final = "critical"

#: The only alerts drawn in the error red. Everything else is wheat.
CRITICAL_ALERTS: Final[frozenset[str]] = frozenset({ALERT_OVERDUE_FIELDS, ALERT_LICENCE_EXPIRY})

#: Named records listed under an alert, so an officer can act without a second screen.
ALERT_SAMPLE_LIMIT: Final = 5

# ------------------------------------------------------------------------ sections

#: Every dashboard response is kept this long, keyed by its own parameters.
CACHE_TTL_SECONDS: Final = 30.0

#: Entries in the recent-activity feed.
ACTIVITY_LIMIT: Final = 25
ACTIVITY_MAX_LIMIT: Final = 100

#: Districts (cotton) or counties (hemp) in the top-regions chart.
TOP_REGIONS: Final = 8

#: Heaps and batches in the utilisation chart, largest input first.
HEAP_CHART_LIMIT: Final = 12

#: Fields drawn on the overview map, as on the radar's map.
MAP_FEATURE_LIMIT: Final = 2000

#: Points a time series may return, so a wide custom range cannot grow without bound.
TIMESERIES_MAX_POINTS: Final = 400

# -------------------------------------------------------------------------- ranges

RANGE_7D: Final = "7d"
RANGE_30D: Final = "30d"
RANGE_SEASON: Final = "season"
RANGE_CUSTOM: Final = "custom"
RANGES: Final[tuple[str, ...]] = (RANGE_7D, RANGE_30D, RANGE_SEASON, RANGE_CUSTOM)

#: Days each preset covers, counting today.
RANGE_DAYS: Final[dict[str, int]] = {RANGE_7D: 7, RANGE_30D: 30}

#: The widest custom range, so one request cannot ask for a decade of days.
MAX_CUSTOM_RANGE_DAYS: Final = 732

# --------------------------------------------------------------------------- units

#: Area and mass shown per crop programme (the same split the rest of the product uses).
AREA_UNIT: Final[dict[str, str]] = {"cotton": "acre", "hemp": "ha"}
MASS_UNIT: Final[dict[str, str]] = {"cotton": "maund", "hemp": "t"}

CROPS: Final[tuple[str, ...]] = ("cotton", "hemp")
CROP_ALL: Final = "all"
SCOPE_MINE: Final = "mine"
SCOPE_ALL: Final = "all"
