"""Pydantic schemas for Module 9 (Gate Reception)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GateEntryOut(BaseModel):
    """One gate entry, with the site's code and name resolved for the screen."""

    id: str
    delivery_id: str
    delivery_no: str
    site_id: str
    site_code: str | None
    site_name: str | None
    crop: str
    status: str
    arrived_at: datetime
    vehicle_no: str
    driver_name: str
    gross_weight_kg: float | None
    tare_weight_kg: float | None
    net_weight_kg: float | None
    moisture_pct: float | None
    accepted_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    note: str | None
    can_accept: bool
    can_reject: bool
    # The delivery's reference weight and the tolerances in force, so the gate can
    # preview the variance before accepting. Null once the entry is decided.
    field_weight_kg: float | None
    estimated_quantity_kg: float | None
    variance_warn_pct: float | None
    variance_flag_pct: float | None
    moisture_warn_pct: float | None


class GateEntryPageOut(BaseModel):
    items: list[GateEntryOut]
    total: int


class InboundLoadOut(BaseModel):
    """An in-transit delivery heading to the site that has not reached the gate yet."""

    delivery_id: str
    delivery_no: str
    field_code: str
    farmer_id: str
    farmer_name: str | None
    sawie_id: int | None
    crop: str
    site_id: str
    vehicle_no: str
    driver_name: str
    dispatched_at: datetime | None
    estimated_quantity_kg: float | None
    field_weight_kg: float | None


class GateSummaryOut(BaseModel):
    inbound: int
    pending: int
    accepted_today: int
    rejected_today: int
    net_kg_today: float


class GateEntryCreate(BaseModel):
    delivery_id: str = Field(..., min_length=1, max_length=36)
    note: str | None = Field(None, max_length=1000)


class GateAccept(BaseModel):
    gross_weight_kg: float = Field(..., gt=0, le=200_000)
    tare_weight_kg: float = Field(..., ge=0, le=50_000)
    moisture_pct: float = Field(..., ge=0, le=100)
    note: str | None = Field(None, max_length=1000)


class GateReject(BaseModel):
    rejection_reason: str = Field(..., min_length=3, max_length=500)


class GateAcceptOut(BaseModel):
    entry: GateEntryOut
    warnings: list[str]
