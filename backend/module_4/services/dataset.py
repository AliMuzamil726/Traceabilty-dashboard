"""Assemble Radar rows from Modules 2 and 3 in a fixed number of queries.

One query for the fields and farmers (``module_2.public_api.list_field_sources``), a few
for the fieldbook facts (``module_3.public_api.get_crop_status_bulk``), one for the
clocks, one for pickup requests and two small ones for officer and office names. The
cost does not grow with the number of fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Any

from sqlalchemy.orm import Session

from module_2 import public_api as farms
from module_3 import public_api as fieldbooks
from module_4.models import STATUS_FULFILLED, STATUS_REQUESTED, STATUS_SCHEDULED
from module_4.repository import PickupRequestRepository
from module_4.services import config
from module_4.services.readiness import ClockDays, Readiness, assess
from shared.repositories.officers import OfficerRepository
from shared.repositories.offices import FieldOfficeRepository

PICKUP_NONE = "not_requested"
PICKUP_REQUESTED = "requested"
PICKUP_SCHEDULED = "scheduled"
PICKUP_DELIVERED = "delivered"
PICKUP_STATES = (PICKUP_NONE, PICKUP_REQUESTED, PICKUP_SCHEDULED, PICKUP_DELIVERED)
_PICKUP_FROM_STATUS = {
    STATUS_REQUESTED: PICKUP_REQUESTED,
    STATUS_SCHEDULED: PICKUP_SCHEDULED,
    STATUS_FULFILLED: PICKUP_DELIVERED,
}


@dataclass(frozen=True)
class RadarRow:
    field_id: str
    field_code: str
    farmer_id: str
    sawie_id: int
    farmer_name: str
    father_or_farm: str | None
    crop: str
    country: str
    district: str | None
    tehsil: str | None
    village: str | None
    county: str | None
    region: str | None
    location: str
    field_office_id: str
    field_office_name: str | None
    officer_id: str | None
    officer_name: str | None
    area_acre: float
    area_ha: float
    centroid_lat: float
    centroid_lng: float
    fieldbook_id: str | None
    #: ``draft``, ``submitted`` or None when the field has no fieldbook this season.
    fieldbook_status: str | None
    sowing_date: date | None
    readiness: Readiness
    estimated_kg: float | None
    estimate_is_benchmark: bool
    pickup_state: str
    request_id: str | None
    request_no: str | None
    geometry: dict[str, Any] | None

    @property
    def status(self) -> str:
        return self.readiness.bucket

    @property
    def has_open_request(self) -> bool:
        return self.pickup_state in (PICKUP_REQUESTED, PICKUP_SCHEDULED)


def centroid(geometry: dict[str, Any] | None, fallback: tuple[float, float]) -> tuple[float, float]:
    """Area centroid (lat, lng) of a GeoJSON Polygon's outer ring."""
    try:
        ring = geometry["coordinates"][0]  # type: ignore[index]
    except (TypeError, KeyError, IndexError):
        return fallback
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in pairwise(ring):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area) < 1e-18:
        return fallback
    return (round(cy / (3 * area), 7), round(cx / (3 * area), 7))


def _location(src: farms.FieldSourceDTO) -> str:
    parts = (
        [src.village, src.tehsil, src.district]
        if src.crop == "cotton"
        else [src.county, src.region]
    )
    return ", ".join(p for p in parts if p) or "-"


def build_rows(
    session: Session,
    *,
    crop: str,
    season_year: int,
    today: date,
    include_geometry: bool = True,
) -> list[RadarRow]:
    sources = farms.list_field_sources(session, crop=crop, include_geometry=include_geometry)
    pairs = [(s.id, season_year) for s in sources]
    facts = fieldbooks.get_crop_status_bulk(session, pairs, today=today)
    clocks = fieldbooks.get_crop_clocks(session)
    requests = PickupRequestRepository(session).latest_by_field(season_year, crop=crop)
    officers = {o.id: o.full_name for o in OfficerRepository(session).list_all()}
    offices = {o.id: o.name for o in FieldOfficeRepository(session).list_all()}
    benchmark_kg, benchmark_unit = config.BENCHMARK_KG[crop]

    clock = clocks[crop]
    days = ClockDays(clock.approach_day, clock.ready_day, clock.window_end_day)
    rows: list[RadarRow] = []
    for src in sources:
        fact = facts[(src.id, season_year)]
        readiness = assess(
            days,
            fact.sowing_date,
            today,
            harvested=fact.harvested,
            ready_flag=fact.ready_for_pickup,
        )
        if fact.estimated_kg:
            estimate, benchmark = fact.estimated_kg, False
        else:
            area = src.area_acre if benchmark_unit == "acre" else src.area_ha
            estimate, benchmark = round(benchmark_kg * area, 1), True
        request = requests.get(src.id)
        pickup = _PICKUP_FROM_STATUS.get(request.status, PICKUP_NONE) if request else PICKUP_NONE
        lat, lng = centroid(src.geometry, (src.pin_lat, src.pin_lng))
        rows.append(
            RadarRow(
                field_id=src.id,
                field_code=src.field_id,
                farmer_id=src.farmer_id,
                sawie_id=src.sawie_id,
                farmer_name=src.farmer_name,
                father_or_farm=src.father_name if crop == "cotton" else src.farm_name,
                crop=src.crop,
                country=src.country,
                district=src.district,
                tehsil=src.tehsil,
                village=src.village,
                county=src.county,
                region=src.region,
                location=_location(src),
                field_office_id=src.field_office_id,
                field_office_name=offices.get(src.field_office_id),
                officer_id=src.registered_by,
                officer_name=officers.get(src.registered_by or ""),
                area_acre=src.area_acre,
                area_ha=src.area_ha,
                centroid_lat=lat,
                centroid_lng=lng,
                fieldbook_id=fact.fieldbook_id,
                fieldbook_status=fact.fieldbook_status,
                sowing_date=fact.sowing_date,
                readiness=readiness,
                estimated_kg=estimate,
                estimate_is_benchmark=benchmark,
                pickup_state=pickup if request and pickup != PICKUP_NONE else PICKUP_NONE,
                request_id=request.id if request and request.status != "cancelled" else None,
                request_no=request.request_no
                if request and request.status != "cancelled"
                else None,
                geometry=src.geometry,
            )
        )
    return rows
