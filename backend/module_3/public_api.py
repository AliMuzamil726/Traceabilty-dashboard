"""Public API of Module 3 (Fieldbook).

The ONLY file other modules may import from this module. Functions take a ``Session``
plus plain arguments and return frozen dataclasses. ``field_id`` everywhere is Module
2's field primary key, the same value Module 2's guards and events carry.
Signatures are documented in ``docs/CONTRACTS.md``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from module_3.config_api import (
    get_config,
    preview_config_change,
    update_config,
)
from module_3.models import STATUS_SUBMITTED, STEP_COMPLETE, STEP_NOT_APPLICABLE, Fieldbook
from module_3.repository import (
    CropClockRepository,
    EntryRepository,
    FieldbookRepository,
    StepStatusRepository,
)
from module_3.services import clock as clocks
from module_3.services import formschema as fs


@dataclass(frozen=True)
class FieldbookSummaryDTO:
    id: str
    field_id: str
    field_code: str
    farmer_id: str
    crop: str
    season_year: int
    status: str
    locked: bool
    schema_version: str
    steps_complete: int
    steps_total: int
    submitted_at: datetime | None
    ready_for_pickup_at: datetime | None


@dataclass(frozen=True)
class CropClockDTO:
    crop: str
    approach_day: int
    ready_day: int
    window_end_day: int


@dataclass(frozen=True)
class CropStatusDTO:
    field_id: str
    season_year: int
    status: str  # no_sowing_data, growing, approaching, ready, harvested
    label: str
    days_after_sowing: int | None
    sowing_date: date | None
    overdue: bool
    next_milestone: str


@dataclass(frozen=True)
class ReadyForPickupDTO:
    fieldbook_id: str
    field_id: str
    field_code: str
    farmer_id: str
    crop: str
    season_year: int
    entry_index: int
    picking_number: str | int | None
    estimated_kg: float | None
    ready_for_pickup_at: datetime | None


@dataclass(frozen=True)
class TimelineEventDTO:
    at: datetime
    step_key: str | None
    kind: str
    summary: str
    officer_id: str | None


@dataclass(frozen=True)
class EstimatedYieldDTO:
    field_id: str
    season_year: int
    crop: str
    #: Cotton: sum of picking yields times area sown, in kg (40 kg per maund).
    #: Hemp: seed yield plus total baled straw, in kg.
    estimated_kg: float | None
    seed_kg: float | None
    straw_kg: float | None
    yield_maunds_per_acre: float | None
    area: float | None
    area_unit: str


@dataclass(frozen=True)
class FieldCropFactsDTO:
    """What a fieldbook says about one field and season, for bulk readers such as Radar.

    ``status`` and friends are Module 3's own crop status; the raw facts beside them
    (sowing date, harvested, ready flag, yield) let a reader apply its own rules.
    """

    field_id: str
    season_year: int
    fieldbook_id: str | None
    fieldbook_status: str | None  # draft, submitted, or None when there is no book
    crop: str | None
    sowing_date: date | None
    days_after_sowing: int | None
    harvested: bool
    ready_for_pickup: bool
    ready_for_pickup_at: datetime | None
    estimated_kg: float | None
    status: str
    overdue: bool
    next_milestone: str


@dataclass(frozen=True)
class StepCompletionDTO:
    """One step of a crop's form and how far the season's fieldbooks have got with it.

    Added for Module 1's completion funnel (D-096). ``order`` is the step's position in
    the crop's definition, so a caller can draw the funnel without re-reading the form.
    """

    step_key: str
    title: str
    order: int
    repeatable: bool
    #: Fieldbooks whose step is complete or marked "nothing to record for this step".
    complete: int


@dataclass(frozen=True)
class StaleDraftDTO:
    """A draft fieldbook nobody has touched lately. Added for Module 1's alerts."""

    fieldbook_id: str
    field_id: str
    field_code: str
    farmer_id: str
    crop: str
    season_year: int
    updated_at: datetime
    steps_complete: int
    steps_total: int


@dataclass(frozen=True)
class LicenceExpiryDTO:
    """A hemp grower's Home Office licence expiry, as recorded in the fieldbook.

    The expiry date is only ever entered on the hemp fieldbook's first step, so this is
    where Module 1 reads it from (D-098). ``expiry`` is None when the step has not been
    filled in yet.
    """

    fieldbook_id: str
    field_id: str
    field_code: str
    farmer_id: str
    season_year: int
    licence_no: str | None
    expiry: date | None


def _book(session: Session, field_id: str, season_year: int) -> Fieldbook | None:
    book = FieldbookRepository(session).for_field(field_id, int(season_year))
    return book if book is not None and book.deleted_at is None else None


def _single(session: Session, book: Fieldbook) -> dict[str, dict[str, Any]]:
    definition = fs.load_definition(book.crop)
    repeatable = {s["key"] for s in definition["steps"] if s["repeatable"]}
    return {
        e.step_key: e.data
        for e in EntryRepository(session).for_book(book.id)
        if e.step_key not in repeatable
    }


def _sowing(session: Session, book: Fieldbook) -> date | None:
    ref = fs.load_definition(book.crop)["sowing_date_ref"]
    _, step, field = fs.ref_parts(ref)
    return fs.parse_date((_single(session, book).get(step) or {}).get(field))


def has_fieldbook(session: Session, field_id: str, season_year: int) -> bool:
    return _book(session, field_id, season_year) is not None


def get_fieldbook_summary(
    session: Session, field_id: str, season_year: int
) -> FieldbookSummaryDTO | None:
    book = _book(session, field_id, season_year)
    if book is None:
        return None
    definition = fs.load_definition(book.crop)
    statuses = StepStatusRepository(session).for_book(book.id)
    done = sum(1 for s in statuses.values() if s.status in ("complete", STEP_NOT_APPLICABLE))
    return FieldbookSummaryDTO(
        id=book.id,
        field_id=book.field_id,
        field_code=book.field_code,
        farmer_id=book.farmer_id,
        crop=book.crop,
        season_year=book.season_year,
        status=book.status,
        locked=book.locked,
        schema_version=book.schema_version,
        steps_complete=done,
        steps_total=len(definition["steps"]),
        submitted_at=book.submitted_at,
        ready_for_pickup_at=book.ready_for_pickup_at,
    )


def get_sowing_date(session: Session, field_id: str, season_year: int) -> date | None:
    book = _book(session, field_id, season_year)
    return _sowing(session, book) if book else None


def get_crop_clock(session: Session, crop: str) -> CropClockDTO | None:
    row = CropClockRepository(session).for_crop(crop)
    if row is not None:
        return CropClockDTO(row.crop, row.approach_day, row.ready_day, row.window_end_day)
    if crop in clocks.DEFAULT_CLOCKS:
        a, r, w = clocks.DEFAULT_CLOCKS[crop]
        return CropClockDTO(crop, a, r, w)
    return None


def get_crop_status(
    session: Session, field_id: str, season_year: int, *, today: date | None = None
) -> CropStatusDTO | None:
    book = _book(session, field_id, season_year)
    if book is None:
        return None
    clock = get_crop_clock(session, book.crop)
    assert clock is not None
    harvest = fs.load_definition(book.crop)["harvest_step"]
    harvested = bool(EntryRepository(session).for_step(book.id, harvest))
    status = clocks.crop_status(
        clocks.Clock(clock.crop, clock.approach_day, clock.ready_day, clock.window_end_day),
        _sowing(session, book),
        today or date.today(),
        harvested=harvested,
    )
    return CropStatusDTO(
        field_id=field_id,
        season_year=season_year,
        status=status.status,
        label=status.label,
        days_after_sowing=status.days_after_sowing,
        sowing_date=status.sowing_date,
        overdue=status.overdue,
        next_milestone=status.next_milestone,
    )


def _entry_kg(
    book: Fieldbook, data: dict[str, Any], single: dict[str, dict[str, Any]]
) -> float | None:
    if book.crop == "cotton":
        area = (single.get("field_info") or {}).get("area_sown")
        if data.get("yield") is None or area is None:
            return None
        return round(float(data["yield"]) * float(area) * 40.0, 1)
    weight = data.get("total_straw_weight")
    return float(weight) if weight is not None else None


def list_ready_for_pickup(
    session: Session,
    *,
    crop: str | None = None,
    season_year: int | None = None,
    farmer_id: str | None = None,
) -> list[ReadyForPickupDTO]:
    """Every harvest (cotton) or baling (hemp) entry marked ready for pickup."""
    out: list[ReadyForPickupDTO] = []
    entries = EntryRepository(session)
    for book in FieldbookRepository(session).with_pickup(crop=crop, season_year=season_year):
        if farmer_id and book.farmer_id != farmer_id:
            continue
        pickup = fs.load_definition(book.crop)["pickup"]
        single = _single(session, book)
        for entry in entries.for_step(book.id, pickup["step"]):
            if entry.data.get(pickup["field"]) != "yes":
                continue
            label_field = pickup.get("label_field")
            out.append(
                ReadyForPickupDTO(
                    fieldbook_id=book.id,
                    field_id=book.field_id,
                    field_code=book.field_code,
                    farmer_id=book.farmer_id,
                    crop=book.crop,
                    season_year=book.season_year,
                    entry_index=entry.entry_index,
                    picking_number=entry.data.get(label_field)
                    if label_field
                    else entry.entry_index + 1,
                    estimated_kg=_entry_kg(book, entry.data, single),
                    ready_for_pickup_at=book.ready_for_pickup_at,
                )
            )
    return out


def get_activity_timeline(
    session: Session, field_id: str, season_year: int
) -> list[TimelineEventDTO]:
    from module_3.services.books import FieldbookService, build_timeline

    book = _book(session, field_id, season_year)
    if book is None:
        return []
    service = FieldbookService(session)
    items = build_timeline(
        service, book, fs.load_definition(book.crop), EntryRepository(session).for_book(book.id)
    )
    return [
        TimelineEventDTO(
            at=i.at, step_key=i.step_key, kind=i.kind, summary=i.summary, officer_id=i.officer_id
        )
        for i in items
    ]


def get_estimated_yield(
    session: Session, field_id: str, season_year: int
) -> EstimatedYieldDTO | None:
    book = _book(session, field_id, season_year)
    if book is None:
        return None
    single = _single(session, book)
    entries = EntryRepository(session)
    if book.crop == "cotton":
        area = (single.get("field_info") or {}).get("area_sown")
        pickings = entries.for_step(book.id, "harvest")
        per_acre = sum(float(e.data.get("yield") or 0) for e in pickings) if pickings else None
        kg = round(per_acre * float(area) * 40.0, 1) if per_acre is not None and area else None
        return EstimatedYieldDTO(
            field_id,
            int(season_year),
            "cotton",
            kg,
            None,
            None,
            per_acre,
            float(area) if area else None,
            "acre",
        )
    harvest = single.get("harvest") or {}
    seed = float(harvest["seed_yield"]) if harvest.get("seed_yield") is not None else None
    bales = entries.for_step(book.id, "baling")
    straw = sum(float(e.data.get("total_straw_weight") or 0) for e in bales) if bales else None
    parts = [v for v in (seed, straw) if v is not None]
    area = (single.get("field_info") or {}).get("area_drilled")
    return EstimatedYieldDTO(
        field_id,
        int(season_year),
        "hemp",
        sum(parts) if parts else None,
        seed,
        straw,
        None,
        float(area) if area else None,
        "ha",
    )


def _estimate_kg(
    crop: str, single: dict[str, dict[str, Any]], by_step: dict[str, list[dict[str, Any]]]
) -> float | None:
    """Cotton: picking yields x area sown x 40 kg per maund. Hemp: seed plus baled straw."""
    if crop == "cotton":
        area = (single.get("field_info") or {}).get("area_sown")
        pickings = by_step.get("harvest") or []
        if not pickings or not area:
            return None
        per_acre = sum(float(d.get("yield") or 0) for d in pickings)
        return round(per_acre * float(area) * 40.0, 1)
    harvest = single.get("harvest") or {}
    seed = float(harvest["seed_yield"]) if harvest.get("seed_yield") is not None else None
    bales = by_step.get("baling") or []
    straw = sum(float(d.get("total_straw_weight") or 0) for d in bales) if bales else None
    parts = [v for v in (seed, straw) if v is not None]
    return round(sum(parts), 1) if parts else None


def get_crop_status_bulk(
    session: Session,
    pairs: Sequence[tuple[str, int]],
    *,
    today: date | None = None,
) -> dict[tuple[str, int], FieldCropFactsDTO]:
    """Crop facts for many (field_id, season_year) pairs at once.

    A fixed number of queries whatever the number of pairs (one for the books, one for
    their entries, one for the clocks, each chunked for very long lists), so a caller
    listing a thousand fields never makes a call per field. Every pair is answered;
    a field without a fieldbook comes back as ``no_sowing_data`` with no book id.
    """
    today = today or date.today()
    books = FieldbookRepository(session).active_for_pairs(pairs)
    entries = EntryRepository(session).for_books([b.id for b in books.values()])
    clock_rows = CropClockRepository(session).all()

    def clock_for(crop: str) -> clocks.Clock:
        row = clock_rows.get(crop)
        if row is not None:
            return clocks.Clock(crop, row.approach_day, row.ready_day, row.window_end_day)
        a, r, w = clocks.DEFAULT_CLOCKS[crop]
        return clocks.Clock(crop, a, r, w)

    out: dict[tuple[str, int], FieldCropFactsDTO] = {}
    for field_id, year in pairs:
        key = (field_id, int(year))
        book = books.get(key)
        if book is None:
            status = clocks.crop_status(clock_for("cotton"), None, today)
            out[key] = FieldCropFactsDTO(
                field_id,
                int(year),
                None,
                None,
                None,
                None,
                None,
                False,
                False,
                None,
                None,
                status.status,
                False,
                status.next_milestone,
            )
            continue
        definition = fs.load_definition(book.crop)
        repeatable = {s["key"] for s in definition["steps"] if s["repeatable"]}
        single: dict[str, dict[str, Any]] = {}
        by_step: dict[str, list[dict[str, Any]]] = {}
        for entry in entries.get(book.id, []):
            if entry.step_key in repeatable:
                by_step.setdefault(entry.step_key, []).append(entry.data)
            else:
                single[entry.step_key] = entry.data
        _, step, field = fs.ref_parts(definition["sowing_date_ref"])
        sowing = fs.parse_date((single.get(step) or {}).get(field))
        harvest_step, pickup = definition["harvest_step"], definition["pickup"]
        harvested = bool(single.get(harvest_step) or by_step.get(harvest_step)) or bool(
            by_step.get(pickup["step"]) or single.get(pickup["step"])
        )
        pickup_rows = by_step.get(pickup["step"]) or (
            [single[pickup["step"]]] if pickup["step"] in single else []
        )
        ready_flag = any(d.get(pickup["field"]) == "yes" for d in pickup_rows)
        status = clocks.crop_status(clock_for(book.crop), sowing, today, harvested=harvested)
        out[key] = FieldCropFactsDTO(
            field_id=field_id,
            season_year=int(year),
            fieldbook_id=book.id,
            fieldbook_status=book.status,
            crop=book.crop,
            sowing_date=sowing,
            days_after_sowing=(today - sowing).days if sowing else None,
            harvested=harvested,
            ready_for_pickup=ready_flag,
            ready_for_pickup_at=book.ready_for_pickup_at,
            estimated_kg=_estimate_kg(book.crop, single, by_step),
            status=status.status,
            overdue=status.overdue,
            next_milestone=status.next_milestone,
        )
    return out


def get_crop_clocks(session: Session) -> dict[str, CropClockDTO]:
    """Every crop's clock in one query (defaults fill any crop without a row)."""
    rows = CropClockRepository(session).all()
    out = {crop: CropClockDTO(crop, a, r, w) for crop, (a, r, w) in clocks.DEFAULT_CLOCKS.items()}
    for crop, row in rows.items():
        out[crop] = CropClockDTO(crop, row.approach_day, row.ready_day, row.window_end_day)
    return out


# --------------------------------------------------------------------- aggregates
# Added for Module 1 (Dashboard, D-096). Counts are computed in SQL; the two listing
# functions return small, threshold-bounded sets for the attention panel.

#: Step statuses that count as finished for the funnel.
_DONE_STATUSES = (STEP_COMPLETE, STEP_NOT_APPLICABLE)


def count_fieldbooks_by_status(
    session: Session, *, crop: str | None = None, season_year: int | None = None
) -> dict[str, int]:
    """``{"draft": n, "submitted": n}`` for live fieldbooks. One query."""
    counts = FieldbookRepository(session).count_by_status(crop=crop, season_year=season_year)
    return {"draft": counts.get("draft", 0), "submitted": counts.get(STATUS_SUBMITTED, 0)}


def count_submitted_by_officer(
    session: Session, *, crop: str | None = None, season_year: int | None = None
) -> dict[str, int]:
    """Submitted fieldbooks per submitting officer. One query."""
    return FieldbookRepository(session).count_submitted_by_officer(
        crop=crop, season_year=season_year
    )


def count_step_completion(
    session: Session, *, crop: str, season_year: int | None = None
) -> list[StepCompletionDTO]:
    """Each step of the crop's form with the number of fieldbooks that finished it.

    Steps come from the crop's form definition, in its own order, so the funnel always
    matches the form the officers fill in.
    """
    definition = fs.load_definition(crop)
    done = StepStatusRepository(session).count_done_by_step(
        crop=crop, season_year=season_year, statuses=_DONE_STATUSES
    )
    return [
        StepCompletionDTO(
            step_key=step["key"],
            title=step["title"],
            order=int(step["order"]),
            repeatable=bool(step["repeatable"]),
            complete=done.get(step["key"], 0),
        )
        for step in definition["steps"]
    ]


def list_stale_drafts(
    session: Session,
    *,
    updated_before: datetime,
    crop: str | None = None,
    season_year: int | None = None,
) -> list[StaleDraftDTO]:
    """Draft fieldbooks last changed before ``updated_before``, oldest first."""
    rows = FieldbookRepository(session).stale_drafts(
        updated_before=updated_before, crop=crop, season_year=season_year
    )
    done = StepStatusRepository(session).count_done_by_book(
        [r[0] for r in rows], statuses=_DONE_STATUSES
    )
    totals = {c: len(fs.load_definition(c)["steps"]) for c in {r[4] for r in rows}}
    return [
        StaleDraftDTO(
            fieldbook_id=row[0],
            field_id=row[1],
            field_code=row[2],
            farmer_id=row[3],
            crop=row[4],
            season_year=row[5],
            updated_at=row[6],
            steps_complete=done.get(row[0], 0),
            steps_total=totals[row[4]],
        )
        for row in rows
    ]


def list_licence_expiries(
    session: Session, *, season_year: int | None = None
) -> list[LicenceExpiryDTO]:
    """Every hemp fieldbook's recorded licence expiry, earliest first.

    Hemp only: cotton has no licence step. Fieldbooks whose first step is still empty
    come back with ``expiry=None`` and are left for the caller to ignore.
    """
    rows = FieldbookRepository(session).refs_for_crop_season(
        crop="hemp", season_year=season_year
    )
    data = EntryRepository(session).step_data_for_books([r[0] for r in rows], "field_info")
    out: list[LicenceExpiryDTO] = []
    for row in rows:
        step: dict[str, Any] = data.get(row[0]) or {}
        out.append(
            LicenceExpiryDTO(
                fieldbook_id=row[0],
                field_id=row[1],
                field_code=row[2],
                farmer_id=row[3],
                season_year=row[4],
                licence_no=step.get("licence_no"),
                expiry=fs.parse_date(step.get("licence_expiry")),
            )
        )
    return sorted(out, key=lambda r: (r.expiry or date.max, r.field_code))


def is_submitted(session: Session, field_id: str) -> bool:
    """True when any season's fieldbook for this field is submitted (locked)."""
    return FieldbookRepository(session).has_submitted(field_id)


__all__ = [
    "STATUS_SUBMITTED",
    "CropClockDTO",
    "CropStatusDTO",
    "EstimatedYieldDTO",
    "FieldCropFactsDTO",
    "FieldbookSummaryDTO",
    "LicenceExpiryDTO",
    "ReadyForPickupDTO",
    "StaleDraftDTO",
    "StepCompletionDTO",
    "TimelineEventDTO",
    "count_fieldbooks_by_status",
    "count_step_completion",
    "count_submitted_by_officer",
    "get_activity_timeline",
    "get_config",
    "get_crop_clock",
    "get_crop_clocks",
    "get_crop_status",
    "get_crop_status_bulk",
    "get_estimated_yield",
    "get_fieldbook_summary",
    "get_sowing_date",
    "has_fieldbook",
    "is_submitted",
    "list_licence_expiries",
    "list_ready_for_pickup",
    "list_stale_drafts",
    "preview_config_change",
    "update_config",
]
