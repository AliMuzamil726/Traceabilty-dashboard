"""Response schemas for Module 1 (Dashboard / Home).

The dashboard takes no request bodies: every section is a read. These models describe
what each section returns, so the API documentation is complete and the shapes are
checked rather than trusted.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LinkOut(BaseModel):
    """Where a figure takes you: a frontend route and the filters to open it with."""

    path: str
    params: dict[str, str]


class RangeOut(BaseModel):
    """The time range a section was read with. ``from`` is a reserved word in Python,
    so the field is ``start`` here and ``from`` on the wire."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    start: date = Field(alias="from")
    end: date = Field(alias="to")
    days: int


class SectionBase(BaseModel):
    crop: str
    season_year: int
    scope: str
    generated_at: datetime


# ------------------------------------------------------------------------ overview


class OfficerOut(BaseModel):
    id: str
    full_name: str
    field_office_name: str | None
    is_admin: bool


class FarmerKpiOut(BaseModel):
    total: int
    cotton: int
    hemp: int


class FieldKpiOut(BaseModel):
    total: int
    area: float
    area_unit: str
    area_by_crop: dict[str, float]


class FieldbookKpiOut(BaseModel):
    fields: int
    started: int
    submitted: int
    submitted_pct: float


class ReadyKpiOut(BaseModel):
    fields: int
    estimated_kg: float
    awaiting_pickup: int


class DeliveredKpiOut(BaseModel):
    deliveries: int
    kg: float
    maunds: float | None
    average_moisture_pct: float | None


class BaleKpiOut(BaseModel):
    made: int
    weight_kg: float
    heaps: int


class ScanKpiOut(BaseModel):
    total: int
    in_range: int
    public: int
    internal: int
    active_codes: int
    last_scan_at: datetime | None


class KpisOut(BaseModel):
    farmers: FarmerKpiOut
    fields: FieldKpiOut
    fieldbooks: FieldbookKpiOut
    ready_now: ReadyKpiOut
    delivered: DeliveredKpiOut
    bales: BaleKpiOut
    scans: ScanKpiOut


class UnitsOut(BaseModel):
    area: str
    mass: str


class OverviewOut(SectionBase):
    range: RangeOut
    officer: OfficerOut
    units: UnitsOut
    kpis: KpisOut


# ------------------------------------------------------------------------ pipeline


class StageOut(BaseModel):
    key: str
    title: str
    caption: str
    count: int
    detail: str | None
    conversion_pct: float | None
    progress_pct: float
    link: LinkOut


class PipelineOut(SectionBase):
    stages: list[StageOut]


# --------------------------------------------------------------------------- charts


class PointOut(BaseModel):
    period_start: date
    value: float | None


class SeriesOut(BaseModel):
    key: str
    label: str
    unit: str
    total: float | None
    points: list[PointOut]


class TimeseriesOut(SectionBase):
    model_config = ConfigDict(populate_by_name=True)

    metric: str
    interval: str
    start: date = Field(alias="from")
    end: date = Field(alias="to")
    truncated: bool
    series: list[SeriesOut]


class ReadinessSliceOut(BaseModel):
    bucket: str
    label: str
    fields: int
    area: float
    estimated_kg: float


class FunnelStepOut(BaseModel):
    step_key: str
    title: str
    order: int
    complete: int
    pct: float


class HeapUtilisationOut(BaseModel):
    heap_id: str
    kind: str
    crop: str
    status: str
    input_kg: float
    expected_output_kg: float
    bales_made: int
    max_bales: int
    link: LinkOut


class RegionOut(BaseModel):
    region: str
    fields: int
    area: float


class DistributionOut(SectionBase):
    focus_crop: str
    area_unit: str
    region_label: str
    readiness: list[ReadinessSliceOut]
    fieldbook_funnel: list[FunnelStepOut]
    fieldbooks_started: int
    heap_utilisation: list[HeapUtilisationOut]
    top_regions: list[RegionOut]


# --------------------------------------------------------------------------- alerts


class SampleOut(BaseModel):
    label: str
    sublabel: str | None
    link: LinkOut


class AlertOut(BaseModel):
    key: str
    title: str
    description: str
    count: int
    severity: str
    link: LinkOut
    samples: list[SampleOut]


class AlertsOut(SectionBase):
    total: int
    critical: int
    alerts: list[AlertOut]


# ------------------------------------------------------------------------- activity


class ActivityItemOut(BaseModel):
    id: str
    at: datetime
    module: int
    module_name: str
    entity: str
    entity_id: str
    action: str
    summary: str
    officer_id: str | None
    officer_name: str | None
    link: LinkOut


class ModuleRefOut(BaseModel):
    number: int
    name: str


class ActivityOut(BaseModel):
    module: int | None
    items: list[ActivityItemOut]
    modules: list[ModuleRefOut]
    generated_at: datetime


# ------------------------------------------------------------------------- officers


class OfficerRowOut(BaseModel):
    officer_id: str
    code: str
    full_name: str
    role: str
    country: str
    field_office_name: str | None
    farmers: int
    fields: int
    area: float
    fieldbooks_submitted: int


class OfficerOverviewOut(BaseModel):
    crop: str
    season_year: int
    area_unit: str
    items: list[OfficerRowOut]
    generated_at: datetime


# ----------------------------------------------------------------------- onboarding


class ChecklistStepOut(BaseModel):
    key: str
    title: str
    description: str
    done: bool
    count: int
    link: LinkOut


class OnboardingOut(BaseModel):
    is_empty: bool
    role: str
    scope: str
    crop: str
    season_year: int
    counts: dict[str, int]
    steps: list[ChecklistStepOut]
    generated_at: datetime


__all__ = [
    "ActivityItemOut",
    "ActivityOut",
    "AlertOut",
    "AlertsOut",
    "ChecklistStepOut",
    "DistributionOut",
    "KpisOut",
    "LinkOut",
    "OfficerOverviewOut",
    "OfficerRowOut",
    "OnboardingOut",
    "OverviewOut",
    "PipelineOut",
    "RangeOut",
    "SampleOut",
    "SeriesOut",
    "StageOut",
    "TimeseriesOut",
]
