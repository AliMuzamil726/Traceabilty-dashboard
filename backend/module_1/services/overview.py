"""The header figures and the pipeline tracker.

The pipeline is the dashboard's main element: the seven stages a crop passes through,
each with how many records reached it and what share of the stage before it that is.
The numbers come from :mod:`module_1.services.sources`, so each one is the owning
module's own count and reconciles with that module's screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from module_1 import config
from module_1.services import links, sources
from module_1.services.filters import DashboardFilters
from module_4 import public_api as radar

STAGE_FARMERS = "farmers"
STAGE_FIELDS = "fields"
STAGE_FIELDBOOKS = "fieldbooks"
STAGE_HARVEST = "harvest"
STAGE_DELIVERIES = "deliveries"
STAGE_BALES = "bales"
STAGE_SCANS = "scans"

STAGE_ORDER: tuple[str, ...] = (
    STAGE_FARMERS,
    STAGE_FIELDS,
    STAGE_FIELDBOOKS,
    STAGE_HARVEST,
    STAGE_DELIVERIES,
    STAGE_BALES,
    STAGE_SCANS,
)

#: What each stage counts, in one line, shown under the stage.
STAGE_CAPTIONS: dict[str, str] = {
    STAGE_FARMERS: "People registered in the programme.",
    STAGE_FIELDS: "Boundaries drawn on the map, so a farmer can be followed.",
    STAGE_FIELDBOOKS: "Fields with a season diary started or submitted.",
    STAGE_HARVEST: "Fields ready for pickup or already harvested.",
    STAGE_DELIVERIES: "Loads scheduled, in transit, or weighed in at the gate.",
    STAGE_BALES: "Bales made from the heaps and batches those loads went into.",
    STAGE_SCANS: "Times a code on a bale or heap has been opened.",
}

STAGE_TITLES: dict[str, str] = {
    STAGE_FARMERS: "Farmers registered",
    STAGE_FIELDS: "Fields mapped",
    STAGE_FIELDBOOKS: "Fieldbooks",
    STAGE_HARVEST: "Harvest ready or done",
    STAGE_DELIVERIES: "In Transit / delivered",
    STAGE_BALES: "Heaps and bales produced",
    STAGE_SCANS: "QR codes scanned",
}


@dataclass(frozen=True)
class Stage:
    key: str
    title: str
    caption: str
    count: int
    detail: str | None
    #: Share of the stage before it, or None for the first stage.
    conversion_pct: float | None
    #: Share of the first stage, for the thin bar under the count.
    progress_pct: float
    link: links.Link

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "caption": self.caption,
            "count": self.count,
            "detail": self.detail,
            "conversion_pct": self.conversion_pct,
            "progress_pct": self.progress_pct,
            "link": self.link.as_dict(),
        }


def _pct(part: int, whole: int) -> float | None:
    """A share as a percentage to one decimal, or None when there is nothing to divide."""
    if whole <= 0:
        return None
    return round(part / whole * 100, 1)


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def build_pipeline(
    session: Session, f: DashboardFilters, officer: CurrentOfficer
) -> dict[str, Any]:
    """The seven stages with their counts, conversions and links."""
    registration = sources.registration_view(session, f, officer)
    rows = sources.readiness_rows(session, f, officer)
    delivery = sources.delivery_totals(session, f, officer)
    heaps = sources.heap_rows(session, f)
    scans = sources.scan_totals(session, f)

    with_book = [r for r in rows if r.fieldbook_id is not None]
    submitted = sum(1 for r in with_book if r.fieldbook_status == "submitted")
    drafts = len(with_book) - submitted
    harvest = sum(1 for r in rows if r.status in (radar.STATUS_READY, radar.STATUS_HARVESTED))
    bales = sum(h.bales_made for h in heaps)

    counts: dict[str, int] = {
        STAGE_FARMERS: registration.farmers,
        STAGE_FIELDS: registration.fields,
        STAGE_FIELDBOOKS: len(with_book),
        STAGE_HARVEST: harvest,
        STAGE_DELIVERIES: delivery.delivered,
        STAGE_BALES: bales,
        STAGE_SCANS: scans.total,
    }
    details: dict[str, str | None] = {
        STAGE_FARMERS: (
            f"{registration.farmers_by_crop.get('cotton', 0)} cotton, "
            f"{registration.farmers_by_crop.get('hemp', 0)} hemp"
            if f.crop == config.CROP_ALL
            else None
        ),
        STAGE_FIELDS: f"{registration.area:,.2f} {registration.area_unit} mapped",
        STAGE_FIELDBOOKS: f"{drafts} draft, {submitted} submitted",
        STAGE_HARVEST: _plural(sum(1 for r in rows if r.overdue), "overdue field"),
        STAGE_DELIVERIES: f"{delivery.delivered_kg:,.1f} kg weighed in",
        STAGE_BALES: f"from {_plural(len(heaps), 'heap or batch', 'heaps and batches')}",
        STAGE_SCANS: f"{scans.public} public, {scans.internal} internal",
    }
    stage_links: dict[str, links.Link] = {
        STAGE_FARMERS: links.register(f),
        STAGE_FIELDS: links.register(f),
        STAGE_FIELDBOOKS: links.fieldbook_list(),
        STAGE_HARVEST: links.radar(f, status=radar.STATUS_READY),
        STAGE_DELIVERIES: links.deliveries(f, status="delivered"),
        STAGE_BALES: links.heaps(f),
        STAGE_SCANS: links.qr(f),
    }

    first = counts[STAGE_FARMERS]
    stages: list[Stage] = []
    for index, key in enumerate(STAGE_ORDER):
        previous = counts[STAGE_ORDER[index - 1]] if index else None
        stages.append(
            Stage(
                key=key,
                title=STAGE_TITLES[key],
                caption=STAGE_CAPTIONS[key],
                count=counts[key],
                detail=details[key],
                conversion_pct=None if previous is None else _pct(counts[key], previous),
                progress_pct=min(100.0, _pct(counts[key], first) or 0.0),
                link=stage_links[key],
            )
        )
    return {
        "crop": f.crop,
        "season_year": f.season_year,
        "scope": f.scope,
        "stages": [s.as_dict() for s in stages],
        "generated_at": datetime.now(UTC),
    }


def build_overview(
    session: Session, f: DashboardFilters, officer: CurrentOfficer
) -> dict[str, Any]:
    """The greeting block and the KPI row."""
    window = f.range()
    registration = sources.registration_view(session, f, officer)
    rows = sources.readiness_rows(session, f, officer)
    delivery = sources.delivery_totals(session, f, officer, window=window)
    scans = sources.scan_totals(session, f)
    in_range_scans = sources.scan_totals(session, f, window=window)
    heaps = sources.heap_rows(session, f)

    with_book = [r for r in rows if r.fieldbook_id is not None]
    submitted = sum(1 for r in with_book if r.fieldbook_status == "submitted")
    ready = [r for r in rows if r.status == radar.STATUS_READY]
    cotton_only = f.crop == "cotton"

    return {
        "crop": f.crop,
        "season_year": f.season_year,
        "scope": f.scope,
        "range": {
            "key": window.key,
            "from": window.start,
            "to": window.end,
            "days": window.days,
        },
        "officer": {
            "id": officer.id,
            "full_name": officer.full_name,
            "field_office_name": officer.field_office_name,
            "is_admin": officer.sees_all,
        },
        "units": {"area": registration.area_unit, "mass": f.mass_unit()},
        "kpis": {
            "farmers": {
                "total": registration.farmers,
                "cotton": registration.farmers_by_crop.get("cotton", 0),
                "hemp": registration.farmers_by_crop.get("hemp", 0),
            },
            "fields": {
                "total": registration.fields,
                "area": registration.area,
                "area_unit": registration.area_unit,
                "area_by_crop": registration.area_by_crop,
            },
            "fieldbooks": {
                "fields": len(rows),
                "started": len(with_book),
                "submitted": submitted,
                "submitted_pct": _pct(submitted, len(rows)) or 0.0,
            },
            "ready_now": {
                "fields": len(ready),
                "estimated_kg": round(sum(r.estimated_kg or 0 for r in ready), 1),
                "awaiting_pickup": sum(
                    1 for r in ready if r.pickup_state == radar.PICKUP_NOT_REQUESTED
                ),
            },
            "delivered": {
                "deliveries": delivery.delivered,
                "kg": delivery.delivered_kg,
                "maunds": delivery.delivered_maunds if cotton_only else None,
                "average_moisture_pct": delivery.average_moisture_pct,
            },
            "bales": {
                "made": sum(h.bales_made for h in heaps),
                "weight_kg": float(sum(h.bales_weight_kg for h in heaps)),
                "heaps": len(heaps),
            },
            "scans": {
                "total": scans.total,
                "in_range": in_range_scans.total,
                "public": scans.public,
                "internal": scans.internal,
                "active_codes": scans.active_tokens,
                "last_scan_at": scans.last_scan_at,
            },
        },
        "generated_at": datetime.now(UTC),
    }


__all__ = [
    "STAGE_CAPTIONS",
    "STAGE_ORDER",
    "STAGE_TITLES",
    "Stage",
    "build_overview",
    "build_pipeline",
]
