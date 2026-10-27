"""Request and response schemas for Module 5 (Deliveries)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SiteRefOut(BaseModel):
    id: str
    code: str
    name: str
    type: str
    country: str


class ThresholdsOut(BaseModel):
    variance_warn_pct: float
    variance_flag_pct: float
    moisture_warn_pct: float


class HistoryOut(BaseModel):
    from_status: str | None
    to_status: str
    officer_id: str | None
    officer_name: str | None
    at: datetime
    note: str | None


class DeliveryOut(BaseModel):
    id: str
    delivery_no: str
    pickup_request_id: str
    farmer_id: str
    field_id: str
    field_code: str
    sawie_id: int | None
    farmer_name: str | None
    father_or_farm: str | None
    location: str
    district: str | None
    county: str | None
    officer_name: str | None
    crop: str
    season_year: int
    status: str
    site: SiteRefOut | None
    heap_id: str | None
    scheduled_date: date
    driver_name: str
    driver_phone: str
    vehicle_no: str
    dispatched_at: datetime | None
    delivered_at: datetime | None
    estimated_quantity_kg: float | None
    field_weight_kg: float | None
    weighbridge_weight_kg: float | None
    weighbridge_maunds: float | None
    moisture_pct: float | None
    variance_kg: float | None
    variance_pct: float | None
    variance_level: str | None
    note: str | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime
    can_act: bool


class DeliveryDetailOut(DeliveryOut):
    history: list[HistoryOut]
    thresholds: ThresholdsOut


class DeliveryPageOut(BaseModel):
    items: list[DeliveryOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int]


class InboxItemOut(BaseModel):
    request_id: str
    request_no: str
    field_id: str
    field_code: str
    farmer_id: str
    sawie_id: int | None
    farmer_name: str | None
    location: str
    officer_name: str | None
    crop: str
    season_year: int
    estimated_quantity_kg: float | None
    quantity_is_estimate: bool
    preferred_date: date | None
    note: str | None
    requested_at: datetime
    can_schedule: bool


class ScheduleIn(BaseModel):
    request_ids: list[str] = Field(min_length=1, max_length=200)
    site_id: str = Field(min_length=1, max_length=36)
    scheduled_date: date
    driver_name: str = Field(max_length=120)
    driver_phone: str = Field(max_length=24)
    vehicle_no: str = Field(max_length=24)
    note: str | None = Field(default=None, max_length=1000)


class SkippedOut(BaseModel):
    pickup_request_id: str
    field_code: str | None
    code: str
    reason: str


class ScheduleResultOut(BaseModel):
    created: list[DeliveryOut]
    skipped: list[SkippedOut]


class UpdateIn(BaseModel):
    site_id: str | None = Field(default=None, max_length=36)
    scheduled_date: date | None = None
    driver_name: str | None = Field(default=None, max_length=120)
    driver_phone: str | None = Field(default=None, max_length=24)
    vehicle_no: str | None = Field(default=None, max_length=24)
    note: str | None = Field(default=None, max_length=1000)


class DispatchIn(BaseModel):
    field_weight_kg: float | None = Field(default=None, gt=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=1000)


class ReceiveIn(BaseModel):
    weighbridge_weight_kg: float = Field(le=1_000_000)
    moisture_pct: float
    note: str | None = Field(default=None, max_length=1000)


class CancelIn(BaseModel):
    reason: str = Field(max_length=500)


class CorrectIn(BaseModel):
    reason: str = Field(max_length=1000)
    weighbridge_weight_kg: float | None = Field(default=None, le=1_000_000)
    moisture_pct: float | None = None
    field_weight_kg: float | None = Field(default=None, le=1_000_000)


class TransitionOut(BaseModel):
    delivery: DeliveryDetailOut
    warnings: list[str]


class StatsOut(BaseModel):
    requests_waiting: int
    scheduled: int
    in_transit: int
    delivered_this_week: int
    delivered_this_week_kg: float
    delivered_this_week_maunds: float | None
    weight_flags: int
    week_start: date
