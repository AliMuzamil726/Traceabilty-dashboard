"""Harvest readiness: the single implementation of Radar's status rules.

Every bucket, KPI, filter, map colour, calendar date and pickup check in Module 4 comes
from :func:`assess`. The day counts are never written here: they come from the crop
clock that Module 3 owns (``module_3.public_api.get_crop_clocks``).

Rules, per field and season (days after sowing is DAS):

1. The fieldbook flags Ready for pickup = Yes            -> ready
2. A picking (cotton) or a cutting or baling (hemp) entry -> harvested
3. No fieldbook, or no sowing date                        -> no_sowing_data
4. DAS below the approach day                             -> growing
5. DAS at or above approach and below the ready day       -> approaching
6. DAS at or above the ready day                          -> ready

Overdue is a flag, not a bucket: not harvested and DAS above the window-end day.
The expected ready date is the sowing date plus the ready day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

NO_SOWING = "no_sowing_data"
GROWING = "growing"
APPROACHING = "approaching"
READY = "ready"
HARVESTED = "harvested"
BUCKETS = (NO_SOWING, GROWING, APPROACHING, READY, HARVESTED)
REQUESTABLE = (READY, HARVESTED)

BUCKET_LABELS = {
    NO_SOWING: "No sowing data",
    GROWING: "Growing",
    APPROACHING: "Approaching",
    READY: "Ready",
    HARVESTED: "Harvested",
}


@dataclass(frozen=True)
class ClockDays:
    approach_day: int
    ready_day: int
    window_end_day: int


@dataclass(frozen=True)
class Readiness:
    bucket: str
    days_after_sowing: int | None
    overdue: bool
    expected_ready: date | None
    next_milestone: str
    #: Share of the way from sowing to the end of the harvest window, 0 to 1.
    progress: float | None


def _days(n: int) -> str:
    return "1 day" if n == 1 else f"{n} days"


def assess(
    clock: ClockDays,
    sowing_date: date | None,
    today: date,
    *,
    harvested: bool = False,
    ready_flag: bool = False,
) -> Readiness:
    das = (today - sowing_date).days if sowing_date else None
    expected = sowing_date + timedelta(days=clock.ready_day) if sowing_date else None
    overdue = not harvested and das is not None and das > clock.window_end_day
    progress = None if das is None else max(0.0, min(1.0, das / clock.window_end_day))

    if ready_flag:
        bucket = READY
    elif harvested:
        bucket = HARVESTED
    elif das is None:
        bucket = NO_SOWING
    elif das < clock.approach_day:
        bucket = GROWING
    elif das < clock.ready_day:
        bucket = APPROACHING
    else:
        bucket = READY

    if ready_flag:
        milestone = "Ready for pickup"
    elif harvested:
        milestone = "Harvested"
    elif das is None:
        milestone = "Record the sowing date in Fieldbook"
    elif overdue:
        milestone = f"Overdue by {_days(das - clock.window_end_day)}"
    elif das < clock.ready_day:
        milestone = f"Ready in {_days(clock.ready_day - das)}"
    elif das == clock.window_end_day:
        milestone = "Harvest window closes today"
    else:
        milestone = f"Harvest window closes in {_days(clock.window_end_day - das)}"

    return Readiness(bucket, das, overdue, expected, milestone, progress)
