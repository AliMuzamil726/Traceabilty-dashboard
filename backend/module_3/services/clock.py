"""Crop clock: where a field is in its season, from its sowing date.

``approach_day``, ``ready_day`` and ``window_end_day`` are days after sowing (DAS).
The boundaries are half-open and deliberate, and the tests pin each one:

* DAS < approach_day                    -> Growing
* approach_day <= DAS < ready_day       -> Approaching
* ready_day <= DAS <= window_end_day    -> Ready (the window's last day is still ready)
* DAS > window_end_day                  -> Ready, overdue (the window has closed but
  nothing has been harvested, which is worth saying rather than hiding)
* any harvest recorded                  -> Harvested
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

NO_SOWING = "no_sowing_data"
GROWING = "growing"
APPROACHING = "approaching"
READY = "ready"
HARVESTED = "harvested"

STATUS_LABELS = {
    NO_SOWING: "No sowing data",
    GROWING: "Growing",
    APPROACHING: "Approaching",
    READY: "Ready",
    HARVESTED: "Harvested",
}

#: Seeded defaults, in days after sowing.
DEFAULT_CLOCKS: dict[str, tuple[int, int, int]] = {
    "cotton": (120, 135, 200),
    "hemp": (80, 95, 125),
}


@dataclass(frozen=True)
class Clock:
    crop: str
    approach_day: int
    ready_day: int
    window_end_day: int


@dataclass(frozen=True)
class CropStatus:
    status: str
    label: str
    days_after_sowing: int | None
    sowing_date: date | None
    overdue: bool
    next_milestone: str


def _days(n: int) -> str:
    return "1 day" if n == 1 else f"{n} days"


def crop_status(
    clock: Clock, sowing_date: date | None, today: date, *, harvested: bool = False
) -> CropStatus:
    if sowing_date is None:
        return CropStatus(
            NO_SOWING,
            STATUS_LABELS[NO_SOWING],
            None,
            None,
            False,
            "Record the sowing date to start the crop clock.",
        )
    das = (today - sowing_date).days
    if harvested:
        return CropStatus(
            HARVESTED, STATUS_LABELS[HARVESTED], das, sowing_date, False, "Harvest recorded."
        )
    if das < clock.approach_day:
        return CropStatus(
            GROWING,
            STATUS_LABELS[GROWING],
            das,
            sowing_date,
            False,
            f"Approaching harvest in {_days(clock.approach_day - das)}.",
        )
    if das < clock.ready_day:
        return CropStatus(
            APPROACHING,
            STATUS_LABELS[APPROACHING],
            das,
            sowing_date,
            False,
            f"Ready for harvest in {_days(clock.ready_day - das)}.",
        )
    if das <= clock.window_end_day:
        left = clock.window_end_day - das
        text = (
            "The harvest window closes today."
            if left == 0
            else f"The harvest window closes in {_days(left)}."
        )
        return CropStatus(READY, STATUS_LABELS[READY], das, sowing_date, False, text)
    return CropStatus(
        READY,
        STATUS_LABELS[READY],
        das,
        sowing_date,
        True,
        f"The harvest window ended {_days(das - clock.window_end_day)} ago.",
    )
