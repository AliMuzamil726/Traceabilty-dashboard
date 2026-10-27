"""Request and response schemas for Module 3 (Fieldbook).

Entry payloads are deliberately loose (``dict``) here: their shape is defined by the
form definitions and checked by :mod:`module_3.services.formschema`, so Pydantic does
not hold a second, drifting copy of the rules.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Crop = Literal["cotton", "hemp"]


class OpenBookIn(BaseModel):
    field_id: str = Field(min_length=1, max_length=36)
    season_year: int = Field(ge=2000, le=2100)
    #: Optional. When given it must match the farmer's crop.
    crop: Crop | None = None


class EntryIn(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    crop: Crop | None = None


class NotApplicableIn(BaseModel):
    not_applicable: bool = True
    crop: Crop | None = None


class IssueOut(BaseModel):
    step_key: str
    entry_index: int
    field: str
    level: Literal["error", "warning"]
    message: str


class EntryOut(BaseModel):
    entry_index: int
    data: dict[str, Any]
    completed: bool
    updated_at: datetime
    updated_by: str | None


class StepStateOut(BaseModel):
    key: str
    status: str
    entry_count: int
    entries: list[EntryOut]


class PhotoOut(BaseModel):
    id: str
    original_name: str
    mime: str
    size_bytes: int
    width: int | None
    height: int | None
    uploaded_at: datetime
    url: str
    thumb_url: str


class CropClockOut(BaseModel):
    crop: str
    approach_day: int
    ready_day: int
    window_end_day: int


class CropStatusOut(BaseModel):
    status: str
    label: str
    days_after_sowing: int | None
    sowing_date: date | None
    overdue: bool
    next_milestone: str


class FarmerCardOut(BaseModel):
    id: str
    sawie_id: int
    name: str
    crop: str
    country: str
    registered_by: str | None
    home_office_licence_no: str | None


class FieldCardOut(BaseModel):
    id: str
    field_id: str
    area_acre: float
    area_ha: float


class BookOut(BaseModel):
    """The whole state of one fieldbook, returned by every read and every write."""

    id: str
    field_id: str
    field_code: str
    farmer_id: str
    crop: Crop
    season_year: int
    status: Literal["draft", "submitted"]
    locked: bool
    current_step: str | None
    schema_version: str
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    submitted_at: datetime | None
    submitted_by: str | None
    ready_for_pickup_at: datetime | None
    farmer: FarmerCardOut
    field: FieldCardOut
    #: Values the form pre-fills from other modules (``field.area_acre`` ...).
    defaults: dict[str, Any]
    steps: list[StepStateOut]
    photos: list[PhotoOut]
    warnings: list[IssueOut]
    #: Errors the book carries because of later changes (for example a sowing date
    #: moved after a picking). They block submit.
    errors: list[IssueOut]
    missing_steps: list[str]
    crop_clock: CropClockOut
    crop_status: CropStatusOut


class SaveResultOut(BaseModel):
    book: BookOut
    #: Warnings raised by this save only; the full list is on ``book``.
    warnings: list[IssueOut]


class BookListItemOut(BaseModel):
    id: str
    field_id: str
    field_code: str
    farmer_id: str
    crop: str
    season_year: int
    status: str
    locked: bool
    updated_at: datetime


class TimelineItemOut(BaseModel):
    at: datetime
    step_key: str | None
    step_title: str | None
    entry_index: int | None
    kind: Literal["entry", "not_applicable", "created", "submitted"]
    summary: str
    officer_id: str | None
    officer_name: str | None


class TimelineOut(BaseModel):
    items: list[TimelineItemOut]


class OfficerOptionOut(BaseModel):
    id: str
    code: str
    full_name: str
    role: str
    country: str
    field_office_name: str | None


class FarmerOptionOut(BaseModel):
    id: str
    sawie_id: int
    name: str
    crop: str
    field_count: int
    drafts: int
    submitted: int
    #: ``no_field``, ``not_started``, ``in_progress``, ``submitted``.
    fieldbook_status: str


class FieldOptionOut(BaseModel):
    id: str
    field_id: str
    area_acre: float
    area_ha: float
    fieldbook_id: str | None
    fieldbook_status: str  # none, draft, submitted


class FieldSelectorOut(BaseModel):
    farmer: FarmerCardOut
    season_year: int
    items: list[FieldOptionOut]
