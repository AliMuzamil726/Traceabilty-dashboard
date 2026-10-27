"""Request and response schemas for Module 6 (Heap). Weights are kilograms."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SiteRefOut(BaseModel):
    id: str
    code: str
    name: str
    type: str
    address: str | None


class TotalsOut(BaseModel):
    input_kg: Decimal
    input_maunds: Decimal | None
    outturn_ratio_pct: Decimal
    bale_unit_kg: Decimal
    expected_output_kg: Decimal
    max_bales: int
    bales_made: int
    bales_weight_kg: Decimal
    input_per_bale_kg: Decimal
    remaining_input_kg: Decimal
    remaining_output_kg: Decimal
    consumed_pct: Decimal
    can_close: bool
    can_add_bales: int
    expected_shiv_kg: Decimal | None
    expected_dust_kg: Decimal | None


class HeapListItemOut(BaseModel):
    id: str
    heap_id: str
    site_id: str
    crop: str
    status: str
    opened_at: datetime
    closed_at: datetime | None
    deliveries: int
    input_kg: Decimal
    bales_made: int


class MemberOut(BaseModel):
    delivery_id: str
    delivery_no: str
    farmer_id: str
    field_id: str
    field_code: str
    sawie_id: int | None
    farmer_name: str | None
    village_or_farm: str | None
    delivered_at: datetime | None
    field_weight_kg: float | None
    weighbridge_weight_kg: float | None
    moisture_pct: float | None


class ContributionOut(BaseModel):
    farmer_id: str
    sawie_id: int | None
    farmer_name: str | None
    kg: Decimal
    pct: Decimal
    deliveries: int
    fields: int


class BaleOut(BaseModel):
    id: str
    bale_serial: str
    seq: int
    weight_kg: float
    status: str
    void_reason: str | None
    created_at: datetime
    created_by: str | None
    voided_at: datetime | None


class PermissionsOut(BaseModel):
    can_edit_values: bool
    can_add_deliveries: bool
    can_remove_deliveries: bool
    can_record_bales: bool
    can_void_bales: bool
    can_close: bool
    can_close_with_remainder: bool


class PendingDeliveryOut(BaseModel):
    id: str
    delivery_no: str
    field_code: str
    sawie_id: int | None
    farmer_name: str | None
    village_or_farm: str | None
    delivered_at: datetime | None
    weighbridge_weight_kg: float | None
    moisture_pct: float | None


class HeapDetailOut(BaseModel):
    id: str
    heap_id: str
    crop: str
    status: str
    site: SiteRefOut
    opened_at: datetime
    opened_by_name: str | None
    closed_at: datetime | None
    closed_by_name: str | None
    close_reason: str | None
    outturn_ratio_pct: float
    bale_unit_kg: float
    shiv_pct: float | None
    dust_pct: float | None
    note: str | None
    totals: TotalsOut
    deliveries: list[MemberOut]
    contributions: list[ContributionOut]
    bales: list[BaleOut]
    #: Delivered deliveries at this site and crop not yet in any heap (empty once closed).
    pending_deliveries: list[PendingDeliveryOut]
    permissions: PermissionsOut


class OpenHeapIn(BaseModel):
    site_id: str = Field(min_length=1, max_length=36)
    note: str | None = Field(default=None, max_length=1000)


class OpenHeapOut(BaseModel):
    heap: HeapDetailOut
    warnings: list[str]


class UpdateHeapIn(BaseModel):
    outturn_ratio_pct: float | None = None
    bale_unit_kg: float | None = None
    shiv_pct: float | None = None
    dust_pct: float | None = None
    note: str | None = Field(default=None, max_length=1000)


class AssignIn(BaseModel):
    delivery_ids: list[str] = Field(min_length=1, max_length=500)


class SkippedOut(BaseModel):
    delivery_id: str
    delivery_no: str | None
    code: str
    reason: str


class AssignOut(BaseModel):
    heap: HeapDetailOut
    added: list[str]
    skipped: list[SkippedOut]


class BalesIn(BaseModel):
    count: int = Field(ge=1, le=500)


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=1000)


class CloseIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    with_remainder: bool = False


class HeapConfigOut(BaseModel):
    crop: str
    default_outturn_ratio_pct: float
    default_bale_unit_kg: float
    default_shiv_pct: float | None
    default_dust_pct: float | None
    placeholder: bool = True
