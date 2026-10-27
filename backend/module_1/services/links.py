"""Where a dashboard figure takes you.

Every count, stage and alert on the dashboard is a door into the module that owns the
records behind it, opened with the filters that produced the number. The link targets
are frontend routes and their query keys, which is why they live in one file: when a
module renames a filter, this is the only place that changes.

The keys are the ones each module's own page reads from the web address, so a link
always lands on the same view the officer would have reached by filtering by hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from module_1 import config
from module_1.services.filters import DashboardFilters

REGISTER = "/register"
FIELDBOOK = "/fieldbook"
RADAR = "/radar"
DELIVERIES = "/deliveries"
HEAPS = "/heaps"
QR = "/qr"


@dataclass(frozen=True)
class Link:
    path: str
    params: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return {"path": self.path, "params": dict(self.params)}


def _clean(params: dict[str, str | int | None]) -> dict[str, str]:
    return {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}


def register(f: DashboardFilters | None = None, *, crop: str | None = None) -> Link:
    """The farmer list. A crop narrows it; ``all`` leaves the list unfiltered."""
    chosen = crop or (f.crop if f and f.crop != config.CROP_ALL else None)
    return Link(REGISTER, _clean({"crop": chosen}))


def farmer(farmer_id: str) -> Link:
    """One farmer's profile, which is where a missing field is mapped."""
    return Link(f"{REGISTER}/farmers/{farmer_id}", {})


def fieldbook_list() -> Link:
    return Link(FIELDBOOK, {})


def fieldbook(book_id: str) -> Link:
    """One fieldbook, opened where it was left."""
    return Link(f"{FIELDBOOK}/books/{book_id}", {})


def radar(
    f: DashboardFilters,
    *,
    crop: str | None = None,
    status: str | None = None,
    pickup: str | None = None,
    ready_to: date | None = None,
) -> Link:
    """Harvest Radar. It always needs one crop, so ``all`` falls back to the first."""
    return Link(
        RADAR,
        _clean(
            {
                "crop": crop or f.primary_crop,
                "season": f.season_year,
                "status": status,
                "pickup": pickup,
                "to": ready_to.isoformat() if ready_to else None,
                "scope": f.scope,
            }
        ),
    )


def deliveries(
    f: DashboardFilters,
    *,
    status: str | None = None,
    date_to: date | None = None,
) -> Link:
    """The deliveries list (not the requests inbox), with the filters it reads."""
    return Link(
        DELIVERIES,
        _clean(
            {
                "tab": "deliveries",
                "crop": f.crop if f.crop != config.CROP_ALL else None,
                "status": status,
                "date_to": date_to.isoformat() if date_to else None,
                "scope": f.scope,
            }
        ),
    )


def delivery(delivery_id: str, f: DashboardFilters) -> Link:
    """One delivery, opened in its detail panel."""
    return Link(DELIVERIES, _clean({"tab": "deliveries", "id": delivery_id, "scope": f.scope}))


def heaps(f: DashboardFilters, *, crop: str | None = None, status: str | None = None) -> Link:
    """Heaps and batches. The page shows one crop at a time."""
    return Link(HEAPS, _clean({"crop": crop or f.primary_crop, "status": status}))


def heap(heap_id: str, *, crop: str, site_id: str | None = None) -> Link:
    return Link(HEAPS, _clean({"crop": crop, "site": site_id, "heap": heap_id}))


def qr(f: DashboardFilters, *, crop: str | None = None) -> Link:
    return Link(QR, _clean({"crop": crop or f.primary_crop}))


__all__ = [
    "DELIVERIES",
    "FIELDBOOK",
    "HEAPS",
    "QR",
    "RADAR",
    "REGISTER",
    "Link",
    "deliveries",
    "delivery",
    "farmer",
    "fieldbook",
    "fieldbook_list",
    "heap",
    "heaps",
    "qr",
    "radar",
    "register",
]
