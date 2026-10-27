"""Radar views: filtered rows, bucket counts, KPIs, filter options, map, calendar, CSV.

All views start from the same filtered row set (see :func:`RadarService.view`), so
buckets, KPIs, table, map and calendar always agree.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from core import csvsafe
from core.deps import CurrentOfficer
from core.errors import ValidationAppError
from module_4.services import cache, config
from module_4.services.dataset import PICKUP_STATES, RadarRow, build_rows
from module_4.services.readiness import (
    APPROACHING,
    BUCKET_LABELS,
    BUCKETS,
    GROWING,
    HARVESTED,
    READY,
    REQUESTABLE,
)

SCOPE_MINE = "mine"
SCOPE_ALL = "all"
CROPS = ("cotton", "hemp")

SORT_KEYS: dict[str, Any] = {
    "sawie_id": lambda r: r.sawie_id,
    "farmer": lambda r: r.farmer_name.lower(),
    "field_id": lambda r: r.field_code,
    "location": lambda r: r.location.lower(),
    "officer": lambda r: (r.officer_name or "").lower(),
    "area": lambda r: r.area_acre,
    "sowing_date": lambda r: r.sowing_date or date.max,
    "das": lambda r: (
        r.readiness.days_after_sowing if r.readiness.days_after_sowing is not None else -1
    ),
    "status": lambda r: BUCKETS.index(r.status),
    "expected_ready": lambda r: r.readiness.expected_ready or date.max,
    "pickup": lambda r: PICKUP_STATES.index(r.pickup_state),
    "estimated_kg": lambda r: r.estimated_kg or 0,
}


def today() -> date:
    return datetime.now(UTC).date()


@dataclass(frozen=True)
class RadarFilters:
    crop: str = "cotton"
    season_year: int = field(default_factory=lambda: today().year)
    q: str | None = None
    district: str | None = None
    tehsil: str | None = None
    village: str | None = None
    county: str | None = None
    region: str | None = None
    field_office_id: str | None = None
    officer_id: str | None = None
    status: str | None = None
    pickup: str | None = None
    ready_from: date | None = None
    ready_to: date | None = None
    scope: str = SCOPE_MINE
    field_ids: tuple[str, ...] | None = None

    def validate(self) -> RadarFilters:
        if self.crop not in CROPS:
            raise ValidationAppError("Choose cotton or hemp.", code="radar_crop_invalid")
        if self.status and self.status not in BUCKETS:
            raise ValidationAppError("Unknown status.", code="radar_status_invalid")
        if self.pickup and self.pickup not in PICKUP_STATES:
            raise ValidationAppError("Unknown pickup state.", code="radar_pickup_invalid")
        if self.scope not in (SCOPE_MINE, SCOPE_ALL):
            raise ValidationAppError("Scope is mine or all.", code="radar_scope_invalid")
        return self

    def key(self, officer: CurrentOfficer) -> tuple[Any, ...]:
        return (officer.id, officer.sees_all, *asdict(self).items())


@dataclass(frozen=True)
class Totals:
    fields: int
    area: float
    estimated_kg: float


@dataclass(frozen=True)
class Kpis:
    ready_now: Totals
    approaching_soon: Totals
    pickup_requested: Totals
    overdue: Totals


@dataclass(frozen=True)
class RadarView:
    """Rows after every filter, plus counts over the rows before the status filter."""

    rows: list[RadarRow]
    buckets: dict[str, int]
    kpis: Kpis
    facets: dict[str, Any]
    area_unit: str
    generated_at: datetime


def _totals(rows: list[RadarRow], crop: str) -> Totals:
    area = sum(r.area_acre if config.AREA_UNIT[crop] == "acre" else r.area_ha for r in rows)
    kg = sum(r.estimated_kg or 0 for r in rows)
    return Totals(len(rows), round(area, 2), round(kg, 1))


def _facets(rows: list[RadarRow]) -> dict[str, Any]:
    """Filter options from the data itself, nested for the cascading selects."""

    def distinct(values: Any) -> list[str]:
        return sorted({v for v in values if v})

    return {
        "districts": distinct(r.district for r in rows),
        "tehsils": {
            d: distinct(r.tehsil for r in rows if r.district == d)
            for d in distinct(r.district for r in rows)
        },
        "villages": {
            t: distinct(r.village for r in rows if r.tehsil == t)
            for t in distinct(r.tehsil for r in rows)
        },
        "counties": distinct(r.county for r in rows),
        "regions": distinct(r.region for r in rows),
        "offices": sorted(
            {(r.field_office_id, r.field_office_name or "-") for r in rows}, key=lambda o: o[1]
        ),
        "officers": sorted(
            {(r.officer_id, r.officer_name or "-") for r in rows if r.officer_id},
            key=lambda o: o[1],
        ),
    }


class RadarService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ dataset

    def _db_key(self) -> str:
        return str(self.session.get_bind().url)

    def rows_for(
        self,
        crop: str,
        season_year: int,
        *,
        fresh: bool = False,
        include_geometry: bool = True,
    ) -> list[RadarRow]:
        """The crop's season dataset, cached for 30 seconds.

        ``include_geometry=False`` leaves every field's polygon out. Reading tens of
        thousands of polygons is most of the cost of building this set, and a reader
        that only counts rows does not need them, so the two shapes are cached
        separately (D-106). Every view inside Module 4 uses the full one.
        """

        def compute() -> list[RadarRow]:
            return build_rows(
                self.session,
                crop=crop,
                season_year=season_year,
                today=today(),
                include_geometry=include_geometry,
            )

        if fresh:
            return compute()
        key = ("rows", self._db_key(), crop, season_year, today(), include_geometry)
        return cache.get_or_compute(key, compute)

    @staticmethod
    def can_act(row: RadarRow, officer: CurrentOfficer) -> bool:
        return officer.sees_all or row.officer_id == officer.id

    # ------------------------------------------------------------------ filters

    @staticmethod
    def _match(row: RadarRow, f: RadarFilters, officer: CurrentOfficer) -> bool:
        if f.field_ids is not None and row.field_id not in f.field_ids:
            return False
        if not officer.sees_all and f.scope == SCOPE_MINE and row.officer_id != officer.id:
            return False
        if f.q:
            needle = f.q.strip().lower()
            hay = f"{row.sawie_id} {row.field_code} {row.farmer_name}".lower()
            if needle not in hay:
                return False
        for attr in ("district", "tehsil", "village", "county", "region", "field_office_id"):
            wanted = getattr(f, attr)
            if wanted and getattr(row, attr) != wanted:
                return False
        if f.officer_id and row.officer_id != f.officer_id:
            return False
        if f.pickup and row.pickup_state != f.pickup:
            return False
        expected = row.readiness.expected_ready
        if f.ready_from and (expected is None or expected < f.ready_from):
            return False
        return not (f.ready_to and (expected is None or expected > f.ready_to))

    def view(self, f: RadarFilters, officer: CurrentOfficer) -> RadarView:
        f.validate()

        def compute() -> RadarView:
            base = [r for r in self.rows_for(f.crop, f.season_year) if self._match(r, f, officer)]
            buckets = dict.fromkeys(BUCKETS, 0)
            for r in base:
                buckets[r.status] += 1
            soon = today() + timedelta(days=config.APPROACHING_WINDOW_DAYS)
            kpis = Kpis(
                ready_now=_totals([r for r in base if r.status == READY], f.crop),
                approaching_soon=_totals(
                    [
                        r
                        for r in base
                        if r.status in (GROWING, APPROACHING)
                        and r.readiness.expected_ready is not None
                        and r.readiness.expected_ready <= soon
                    ],
                    f.crop,
                ),
                pickup_requested=_totals([r for r in base if r.has_open_request], f.crop),
                overdue=_totals([r for r in base if r.readiness.overdue], f.crop),
            )
            rows = [r for r in base if not f.status or r.status == f.status]
            return RadarView(
                rows=rows,
                buckets=buckets,
                kpis=kpis,
                facets=_facets(base),
                area_unit=config.AREA_UNIT[f.crop],
                generated_at=datetime.now(UTC),
            )

        return cache.get_or_compute(("view", self._db_key(), today(), *f.key(officer)), compute)

    @staticmethod
    def sort(rows: list[RadarRow], sort: str | None) -> list[RadarRow]:
        key = (sort or "expected_ready").lstrip("-")
        if key not in SORT_KEYS:
            raise ValidationAppError("Unknown sort column.", code="radar_sort_invalid")
        reverse = bool(sort and sort.startswith("-"))
        return sorted(rows, key=lambda r: (SORT_KEYS[key](r), r.field_code), reverse=reverse)

    # ------------------------------------------------------------------ map

    def map_features(self, f: RadarFilters, officer: CurrentOfficer) -> dict[str, Any]:
        rows = self.view(f, officer).rows
        features = []
        for r in rows[: config.MAP_FEATURE_LIMIT]:
            features.append(
                {
                    "type": "Feature",
                    "id": r.field_id,
                    "geometry": r.geometry,
                    "properties": {
                        "field_id": r.field_id,
                        "field_code": r.field_code,
                        "farmer_name": r.farmer_name,
                        "sawie_id": r.sawie_id,
                        "status": r.status,
                        "status_label": BUCKET_LABELS[r.status],
                        "overdue": r.readiness.overdue,
                        "next_milestone": r.readiness.next_milestone,
                        "pickup_state": r.pickup_state,
                        "centroid": [r.centroid_lng, r.centroid_lat],
                        "can_request": self.can_act(r, officer)
                        and r.status in REQUESTABLE
                        and not r.has_open_request,
                    },
                }
            )
        return {
            "type": "FeatureCollection",
            "features": features,
            "total": len(rows),
            "truncated": len(rows) > config.MAP_FEATURE_LIMIT,
        }

    # ------------------------------------------------------------------ calendar

    def calendar(self, f: RadarFilters, officer: CurrentOfficer, month: str) -> dict[str, Any]:
        try:
            first = datetime.strptime(month, "%Y-%m").date()
        except ValueError as exc:
            raise ValidationAppError("Month is YYYY-MM.", code="radar_month_invalid") from exc
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        # The calendar picks its own date range, so it ignores the expected-ready filter.
        rows = [
            r
            for r in self.view(replace(f, ready_from=None, ready_to=None), officer).rows
            if r.readiness.expected_ready is not None and r.status != HARVESTED
        ]
        days: dict[date, list[RadarRow]] = {}
        for r in rows:
            expected = r.readiness.expected_ready
            if expected is not None and first <= expected <= last:
                days.setdefault(expected, []).append(r)
        week0 = today() - timedelta(days=today().weekday())
        weeks = []
        for i in range(8):
            start = week0 + timedelta(weeks=i)
            end = start + timedelta(days=6)
            hits = [r for r in rows if start <= r.readiness.expected_ready <= end]  # type: ignore[operator]
            weeks.append(
                {
                    "week_start": start,
                    "fields": len(hits),
                    "estimated_kg": round(sum(r.estimated_kg or 0 for r in hits), 1),
                }
            )
        return {
            "month": month,
            "days": [
                {
                    "date": d,
                    "fields": len(items),
                    "estimated_kg": round(sum(r.estimated_kg or 0 for r in items), 1),
                }
                for d, items in sorted(days.items())
            ],
            "weeks": weeks,
        }

    # ------------------------------------------------------------------ csv

    def csv_rows(self, f: RadarFilters, officer: CurrentOfficer, sort: str | None) -> Iterator[str]:
        rows = self.sort(self.view(f, officer).rows, sort)
        unit = config.AREA_UNIT[f.crop]
        other = "ha" if unit == "acre" else "acre"
        head = [
            "SAWIE ID",
            "Farmer",
            "Father or farm",
            "Location",
            "Officer",
            "Field ID",
            f"Area ({unit})",
            f"Area ({other})",
            "Sowing date",
            "Days after sowing",
            "Status",
            "Overdue",
            "Expected ready",
            "Pickup state",
            "Next milestone",
            "Estimated quantity (kg)",
            "Quantity is an estimate",
            "Centroid latitude",
            "Centroid longitude",
        ]

        def line(values: list[Any]) -> str:
            buf = io.StringIO()
            csvsafe.writer(buf, lineterminator="\r\n").writerow(values)
            return buf.getvalue()

        yield "﻿" + line(head)
        for r in rows:
            area = (r.area_acre, r.area_ha) if unit == "acre" else (r.area_ha, r.area_acre)
            yield line(
                [
                    r.sawie_id,
                    r.farmer_name,
                    r.father_or_farm or "",
                    r.location,
                    r.officer_name or "",
                    r.field_code,
                    f"{area[0]:.2f}",
                    f"{area[1]:.2f}",
                    r.sowing_date.isoformat() if r.sowing_date else "",
                    "" if r.readiness.days_after_sowing is None else r.readiness.days_after_sowing,
                    BUCKET_LABELS[r.status],
                    "Yes" if r.readiness.overdue else "No",
                    r.readiness.expected_ready.isoformat() if r.readiness.expected_ready else "",
                    r.pickup_state.replace("_", " ").capitalize(),
                    r.readiness.next_milestone,
                    "" if r.estimated_kg is None else f"{r.estimated_kg:.1f}",
                    "Yes" if r.estimate_is_benchmark else "No",
                    f"{r.centroid_lat:.6f}",
                    f"{r.centroid_lng:.6f}",
                ]
            )
