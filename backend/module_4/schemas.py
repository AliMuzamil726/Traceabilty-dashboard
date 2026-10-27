"""Request and response schemas for Module 4 (Harvest Radar)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Crop = Literal["cotton", "hemp"]


class RadarRowOut(BaseModel):
    field_id: str
    field_code: str
    farmer_id: str
    sawie_id: int
    farmer_name: str
    father_or_farm: str | None
    location: str
    district: str | None
    tehsil: str | None
    village: str | None
    county: str | None
    region: str | None
    field_office_id: str
    field_office_name: str | None
    officer_id: str | None
    officer_name: str | None
    area_acre: float
    area_ha: float
    centroid_lat: float
    centroid_lng: float
    fieldbook_id: str | None
    sowing_date: date | None
    days_after_sowing: int | None
    progress: float | None
    status: str
    status_label: str
    overdue: bool
    expected_ready: date | None
    next_milestone: str
    estimated_kg: float | None
    estimate_is_benchmark: bool
    pickup_state: str
    request_id: str | None
    request_no: str | None
    #: The acting officer may request or cancel for this field (own farmer, or admin).
    can_act: bool
    #: Ready or Harvested, with no open request, and the officer may act.
    can_request: bool


class TotalsOut(BaseModel):
    fields: int
    area: float
    estimated_kg: float


class KpisOut(BaseModel):
    ready_now: TotalsOut
    approaching_soon: TotalsOut
    pickup_requested: TotalsOut
    overdue: TotalsOut
    approaching_window_days: int


class OptionOut(BaseModel):
    value: str
    label: str


class FacetsOut(BaseModel):
    districts: list[str]
    tehsils: dict[str, list[str]]
    villages: dict[str, list[str]]
    counties: list[str]
    regions: list[str]
    offices: list[OptionOut]
    officers: list[OptionOut]


class ClockOut(BaseModel):
    approach_day: int
    ready_day: int
    window_end_day: int


class SummaryOut(BaseModel):
    crop: Crop
    season_year: int
    area_unit: str
    buckets: dict[str, int]
    kpis: KpisOut
    clock: ClockOut
    generated_at: datetime
    total_fields: int


class FieldsPageOut(SummaryOut):
    items: list[RadarRowOut]
    total: int
    page: int
    page_size: int
    facets: FacetsOut
    is_admin: bool


class CalendarDayOut(BaseModel):
    date: date
    fields: int
    estimated_kg: float


class CalendarWeekOut(BaseModel):
    week_start: date
    fields: int
    estimated_kg: float


class CalendarOut(BaseModel):
    month: str
    days: list[CalendarDayOut]
    weeks: list[CalendarWeekOut]


class PickupRequestIn(BaseModel):
    crop: Crop
    season_year: int = Field(ge=2000, le=2100)
    field_ids: list[str] = Field(min_length=1, max_length=500)
    preferred_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class PickupRequestOut(BaseModel):
    id: str
    request_no: str
    field_id: str
    field_code: str
    farmer_id: str
    farmer_name: str | None = None
    sawie_id: int | None = None
    crop: str
    season_year: int
    status: str
    estimated_quantity_kg: float | None
    quantity_is_estimate: bool
    preferred_date: date | None
    note: str | None
    requested_by: str | None
    requested_by_name: str | None = None
    requested_at: datetime
    cancelled_by: str | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    delivery_id: str | None
    updated_at: datetime
    can_cancel: bool = False


class SkippedOut(BaseModel):
    field_id: str
    field_code: str | None
    code: str
    reason: str


class PickupResultOut(BaseModel):
    created: list[PickupRequestOut]
    skipped: list[SkippedOut]


class CancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
