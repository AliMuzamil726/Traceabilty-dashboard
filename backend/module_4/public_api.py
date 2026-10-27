"""Public API of Module 4 (Harvest Radar).

The ONLY file other modules may import from this module. Functions take a ``Session``
and return frozen DTOs, never ORM rows. The ``mark_*`` functions change state inside
the caller's transaction and do not commit: the calling module's service commits.
Module 5 (Deliveries) uses them to take open pickup requests and report progress back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from module_4.models import PickupRequest
from module_4.repository import PickupRequestRepository
from module_4.services import cache, config
from module_4.services.dataset import PICKUP_NONE, PICKUP_STATES
from module_4.services.pickups import PickupService
from module_4.services.radar import SCOPE_ALL, RadarFilters, RadarService
from module_4.services.readiness import BUCKET_LABELS, BUCKETS, HARVESTED, READY

# The vocabulary of the values carried in the DTOs below, re-exported so a reader does
# not have to copy the strings or reach into this module's services (D-096).
#: Readiness buckets, in their own order: no_sowing_data, growing, approaching, ready,
#: harvested.
STATUSES: tuple[str, ...] = BUCKETS
#: A readable label per bucket.
STATUS_LABELS: dict[str, str] = dict(BUCKET_LABELS)
#: The two buckets that may be picked up.
STATUS_READY = READY
STATUS_HARVESTED = HARVESTED
#: Pickup states, in their own order: not_requested, requested, scheduled, delivered.
PICKUP_NOT_REQUESTED = PICKUP_NONE
PICKUP_ALL: tuple[str, ...] = PICKUP_STATES


@dataclass(frozen=True)
class PickupRequestDTO:
    id: str
    request_no: str
    field_id: str
    field_code: str
    farmer_id: str
    crop: str
    season_year: int
    status: str  # requested, scheduled, fulfilled, cancelled
    estimated_quantity_kg: float | None
    quantity_is_estimate: bool
    preferred_date: date | None
    note: str | None
    requested_by: str | None
    requested_at: datetime
    cancelled_at: datetime | None
    cancel_reason: str | None
    delivery_id: str | None


@dataclass(frozen=True)
class FieldReadinessDTO:
    field_id: str
    field_code: str
    farmer_id: str
    crop: str
    season_year: int
    status: str  # no_sowing_data, growing, approaching, ready, harvested
    status_label: str
    overdue: bool
    sowing_date: date | None
    days_after_sowing: int | None
    expected_ready: date | None
    next_milestone: str
    estimated_kg: float | None
    estimate_is_benchmark: bool
    pickup_state: str  # not_requested, requested, scheduled, delivered


@dataclass(frozen=True)
class RadarTotalsDTO:
    fields: int
    area: float
    estimated_kg: float


@dataclass(frozen=True)
class RadarSummaryDTO:
    crop: str
    season_year: int
    area_unit: str
    buckets: dict[str, int]
    ready_now: RadarTotalsDTO
    approaching_soon: RadarTotalsDTO
    pickup_requested: RadarTotalsDTO
    overdue: RadarTotalsDTO


@dataclass(frozen=True)
class ReadinessRowDTO:
    """One field's readiness, with everything a programme overview needs beside it.

    Added for Module 1 (Dashboard, D-096). It is the same row the radar's table, map,
    buckets and KPIs are built from, so anything counted here reconciles with Harvest
    Radar by construction. ``ready_since`` is the expected ready date once it has
    passed, which is how long a ready field has been waiting; it is None while the
    field is not ready yet or has no sowing date.
    """

    field_id: str
    field_code: str
    farmer_id: str
    sawie_id: int
    farmer_name: str
    crop: str
    district: str | None
    tehsil: str | None
    village: str | None
    county: str | None
    region: str | None
    location: str
    field_office_id: str
    officer_id: str | None
    officer_name: str | None
    area_acre: float
    area_ha: float
    centroid_lat: float
    centroid_lng: float
    fieldbook_id: str | None
    fieldbook_status: str | None
    sowing_date: date | None
    days_after_sowing: int | None
    status: str
    status_label: str
    overdue: bool
    expected_ready: date | None
    ready_since: date | None
    next_milestone: str
    estimated_kg: float | None
    estimate_is_benchmark: bool
    pickup_state: str
    geometry: dict[str, Any] | None = None


@dataclass(frozen=True)
class RadarQuery:
    """Filters for the read functions. Unset values mean "all"."""

    crop: str = "cotton"
    season_year: int | None = None
    district: str | None = None
    county: str | None = None
    field_office_id: str | None = None
    officer_id: str | None = None
    pickup: str | None = None


# A system reader: sees every field, like an administrator, without being an officer.
_SYSTEM = CurrentOfficer(
    id="system",
    code="SYSTEM",
    full_name="System",
    role="admin",
    country="",
    field_office_id=None,
    field_office_name=None,
)


def _dto(r: PickupRequest) -> PickupRequestDTO:
    return PickupRequestDTO(
        id=r.id,
        request_no=r.request_no,
        field_id=r.field_id,
        field_code=r.field_code,
        farmer_id=r.farmer_id,
        crop=r.crop,
        season_year=r.season_year,
        status=r.status,
        estimated_quantity_kg=r.estimated_quantity_kg,
        quantity_is_estimate=r.quantity_is_estimate,
        preferred_date=r.preferred_date,
        note=r.note,
        requested_by=r.requested_by,
        requested_at=r.requested_at,
        cancelled_at=r.cancelled_at,
        cancel_reason=r.cancel_reason,
        delivery_id=r.delivery_id,
    )


def _filters(query: RadarQuery | None) -> RadarFilters:
    q = query or RadarQuery()
    return RadarFilters(
        crop=q.crop,
        season_year=q.season_year or datetime.now(UTC).year,
        district=q.district,
        county=q.county,
        field_office_id=q.field_office_id,
        officer_id=q.officer_id,
        pickup=q.pickup,
        scope=SCOPE_ALL,
    ).validate()


# --------------------------------------------------------------------------- pickups


def list_open_pickup_requests(
    session: Session, *, crop: str | None = None, season_year: int | None = None
) -> list[PickupRequestDTO]:
    """Requests that are requested or scheduled, oldest first."""
    rows = PickupRequestRepository(session).list_open(crop=crop, season_year=season_year)
    return [_dto(r) for r in rows]


def get_pickup_request(session: Session, request_id: str) -> PickupRequestDTO | None:
    row = PickupRequestRepository(session).get(request_id)
    return _dto(row) if row is not None else None


def mark_pickup_scheduled(session: Session, request_id: str, delivery_id: str) -> PickupRequestDTO:
    return _dto(PickupService(session).mark_scheduled(request_id, delivery_id))


def mark_pickup_fulfilled(session: Session, request_id: str) -> PickupRequestDTO:
    return _dto(PickupService(session).mark_fulfilled(request_id))


def mark_pickup_cancelled(
    session: Session, request_id: str, reason: str, *, officer_id: str | None = None
) -> PickupRequestDTO:
    """Cancel a requested or scheduled request (Module 5 may cancel after scheduling)."""
    service = PickupService(session)
    request = service._require(request_id)
    service.cancel_request(request, reason, officer_id=officer_id, only_requested=False)
    session.flush()
    from module_4.services import cache

    cache.invalidate()
    return _dto(request)


# --------------------------------------------------------------------------- radar


def get_radar_summary(session: Session, query: RadarQuery | None = None) -> RadarSummaryDTO:
    f = _filters(query)
    view = RadarService(session).view(f, _SYSTEM)
    k = view.kpis
    return RadarSummaryDTO(
        crop=f.crop,
        season_year=f.season_year,
        area_unit=config.AREA_UNIT[f.crop],
        buckets=dict(view.buckets),
        ready_now=RadarTotalsDTO(**vars(k.ready_now)),
        approaching_soon=RadarTotalsDTO(**vars(k.approaching_soon)),
        pickup_requested=RadarTotalsDTO(**vars(k.pickup_requested)),
        overdue=RadarTotalsDTO(**vars(k.overdue)),
    )


def count_fields_by_status(session: Session, query: RadarQuery | None = None) -> dict[str, int]:
    """Fields per bucket: no_sowing_data, growing, approaching, ready, harvested."""
    view = RadarService(session).view(_filters(query), _SYSTEM)
    return {b: view.buckets.get(b, 0) for b in BUCKETS}


def get_field_readiness(
    session: Session, field_id: str, season_year: int | None = None
) -> FieldReadinessDTO | None:
    season = season_year or datetime.now(UTC).year
    radar = RadarService(session)
    for crop in ("cotton", "hemp"):
        for row in radar.rows_for(crop, season):
            if row.field_id == field_id:
                r = row.readiness
                return FieldReadinessDTO(
                    field_id=row.field_id,
                    field_code=row.field_code,
                    farmer_id=row.farmer_id,
                    crop=row.crop,
                    season_year=season,
                    status=row.status,
                    status_label=BUCKET_LABELS[row.status],
                    overdue=r.overdue,
                    sowing_date=row.sowing_date,
                    days_after_sowing=r.days_after_sowing,
                    expected_ready=r.expected_ready,
                    next_milestone=r.next_milestone,
                    estimated_kg=row.estimated_kg,
                    estimate_is_benchmark=row.estimate_is_benchmark,
                    pickup_state=row.pickup_state,
                )
    return None


def list_readiness_rows(
    session: Session,
    *,
    crop: str,
    season_year: int | None = None,
    officer_id: str | None = None,
    include_geometry: bool = False,
    today: date | None = None,
) -> list[ReadinessRowDTO]:
    """Every mapped field of a crop and season with its readiness, in a fixed number
    of queries.

    This is the radar's own dataset, cached for 30 seconds like every other radar read,
    so counts taken from it agree with Harvest Radar exactly. ``officer_id`` keeps only
    the fields of the farmers that officer registered, which is what the radar's
    ``scope=mine`` means. ``include_geometry`` adds each field's GeoJSON polygon for a
    map; leave it off for counting.
    """
    season = season_year or datetime.now(UTC).year
    as_of = today or datetime.now(UTC).date()
    key = (
        "readiness_rows",
        str(session.get_bind().url),
        crop,
        season,
        officer_id,
        include_geometry,
        as_of,
    )
    return cache.get_or_compute(
        key, lambda: _readiness_rows(session, crop, season, officer_id, include_geometry, as_of)
    )


def _readiness_rows(
    session: Session,
    crop: str,
    season: int,
    officer_id: str | None,
    include_geometry: bool,
    as_of: date,
) -> list[ReadinessRowDTO]:
    rows = RadarService(session).rows_for(crop, season, include_geometry=include_geometry)
    out: list[ReadinessRowDTO] = []
    for row in rows:
        if officer_id and row.officer_id != officer_id:
            continue
        r = row.readiness
        expected = r.expected_ready
        out.append(
            ReadinessRowDTO(
                field_id=row.field_id,
                field_code=row.field_code,
                farmer_id=row.farmer_id,
                sawie_id=row.sawie_id,
                farmer_name=row.farmer_name,
                crop=row.crop,
                district=row.district,
                tehsil=row.tehsil,
                village=row.village,
                county=row.county,
                region=row.region,
                location=row.location,
                field_office_id=row.field_office_id,
                officer_id=row.officer_id,
                officer_name=row.officer_name,
                area_acre=row.area_acre,
                area_ha=row.area_ha,
                centroid_lat=row.centroid_lat,
                centroid_lng=row.centroid_lng,
                fieldbook_id=row.fieldbook_id,
                fieldbook_status=row.fieldbook_status,
                sowing_date=row.sowing_date,
                days_after_sowing=r.days_after_sowing,
                status=row.status,
                status_label=BUCKET_LABELS[row.status],
                overdue=r.overdue,
                expected_ready=expected,
                ready_since=expected if expected is not None and expected <= as_of else None,
                next_milestone=r.next_milestone,
                estimated_kg=row.estimated_kg,
                estimate_is_benchmark=row.estimate_is_benchmark,
                pickup_state=row.pickup_state,
                geometry=row.geometry if include_geometry else None,
            )
        )
    return out


__all__ = [
    "PICKUP_ALL",
    "PICKUP_NOT_REQUESTED",
    "STATUSES",
    "STATUS_HARVESTED",
    "STATUS_LABELS",
    "STATUS_READY",
    "FieldReadinessDTO",
    "PickupRequestDTO",
    "RadarQuery",
    "RadarSummaryDTO",
    "RadarTotalsDTO",
    "ReadinessRowDTO",
    "count_fields_by_status",
    "get_field_readiness",
    "get_pickup_request",
    "get_radar_summary",
    "list_open_pickup_requests",
    "list_readiness_rows",
    "mark_pickup_cancelled",
    "mark_pickup_fulfilled",
    "mark_pickup_scheduled",
]
