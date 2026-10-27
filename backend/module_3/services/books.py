"""The fieldbook lifecycle: open, fill step by step, submit, and nothing after that.

Every write goes through the same gate, in this order:

1. **access** - the officer registered this farmer, or is an administrator;
2. **lock** - a submitted fieldbook refuses every change (409 ``fieldbook_locked``);
3. **version** - a stale ``X-Fieldbook-Version`` is refused (409 ``fieldbook_stale``),
   so two officers editing the same book cannot overwrite each other silently;
4. **crop** - data sent for the other crop programme is refused;
5. **schema** - the entry is validated against the crop's form definition.

Module 2 is reached only through ``module_2.public_api``; nothing here imports its
internals.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core import audit, events
from core.config import Settings
from core.database import utcnow
from core.deps import CurrentOfficer
from core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from core.events import EventBus
from core.pagination import Page, PageParams
from module_2 import public_api as registry
from module_3 import meta
from module_3.models import (
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STEP_COMPLETE,
    STEP_NOT_APPLICABLE,
    STEP_NOT_STARTED,
    Fieldbook,
    FieldbookEntry,
    FieldbookPhoto,
)
from module_3.repository import (
    CropClockRepository,
    EntryRepository,
    FieldbookRepository,
    PhotoRepository,
    StepStatusRepository,
)
from module_3.schemas import (
    BookListItemOut,
    BookOut,
    CropClockOut,
    CropStatusOut,
    EntryIn,
    EntryOut,
    FarmerCardOut,
    FieldCardOut,
    IssueOut,
    PhotoOut,
    SaveResultOut,
    StepStateOut,
    TimelineItemOut,
    TimelineOut,
)
from module_3.services import clock as clocks
from module_3.services import formschema as fs
from module_3.services import photos as photo_store
from shared.models.officer import SEES_ALL_ROLES
from shared.repositories.master_lists import MasterListRepository
from shared.repositories.officers import OfficerRepository

YES = "yes"


class FieldbookLockedError(AppError):
    status_code = 409
    code = "fieldbook_locked"


def today() -> date:
    return datetime.now(UTC).date()


@dataclass
class _BookContext:
    book: Fieldbook
    definition: dict[str, Any]
    farmer: registry.FarmerDTO
    field: registry.FieldDTO
    season: registry.SeasonProfileDTO | None
    entries: list[FieldbookEntry]


class FieldbookService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        bus: EventBus | None = None,
        upload_root: Path | None = None,
    ) -> None:
        self.session = session
        self.bus = bus or events.bus
        self.upload_root = upload_root or (settings.upload_path if settings else Path("storage"))
        self.books = FieldbookRepository(session)
        self.entries = EntryRepository(session)
        self.statuses = StepStatusRepository(session)
        self.photos = PhotoRepository(session)
        self.clocks = CropClockRepository(session)
        self.master = MasterListRepository(session)
        self.officers = OfficerRepository(session)
        self._options: dict[tuple[str, str, str], set[str]] = {}
        self._labels: dict[tuple[str, str, str], dict[str, str]] = {}

    # ------------------------------------------------------------------ access

    @staticmethod
    def may_access(farmer: registry.FarmerDTO, officer: CurrentOfficer) -> bool:
        return officer.role in SEES_ALL_ROLES or farmer.registered_by == officer.id

    def _require_farmer_access(self, farmer: registry.FarmerDTO, officer: CurrentOfficer) -> None:
        if not self.may_access(farmer, officer):
            raise ForbiddenError(
                "This farmer was registered by another officer. Only that officer or an "
                "administrator can open their fieldbooks.",
                code="fieldbook_forbidden",
                details={"farmer_id": farmer.id},
            )

    def _load(self, book_id: str, officer: CurrentOfficer) -> _BookContext:
        book = self.books.get_active(book_id)
        if book is None:
            raise NotFoundError(
                "That fieldbook does not exist.",
                code="fieldbook_not_found",
                details={"fieldbook_id": book_id},
            )
        farmer = registry.get_farmer(self.session, book.farmer_id)
        field = registry.get_field(self.session, book.field_id)
        if farmer is None or field is None:
            raise NotFoundError(
                "The farmer or field of this fieldbook no longer exists.",
                code="fieldbook_source_missing",
            )
        self._require_farmer_access(farmer, officer)
        season = registry.get_season_profile(self.session, farmer.id, book.season_year)
        return _BookContext(
            book=book,
            definition=fs.load_definition(book.crop),
            farmer=farmer,
            field=field,
            season=season,
            entries=self.entries.for_book(book.id),
        )

    def _guard_write(
        self, ctx: _BookContext, *, version: int | None, crop: str | None = None
    ) -> None:
        book = ctx.book
        if book.locked:
            raise FieldbookLockedError(
                "This fieldbook was submitted and is permanently read-only.",
                details={"fieldbook_id": book.id, "submitted_at": book.submitted_at},
            )
        if version is not None and version != book.version:
            raise ConflictError(
                "This fieldbook was changed by someone else since you opened it. Reload it "
                "to see the latest version, then make your change again.",
                code="fieldbook_stale",
                details={"expected": version, "current": book.version},
            )
        if crop is not None and crop != book.crop:
            raise ConflictError(
                f"This is a {book.crop} fieldbook; {crop} data cannot be saved to it.",
                code="fieldbook_crop_mismatch",
                details={"fieldbook_crop": book.crop, "sent_crop": crop},
            )

    # -------------------------------------------------------------- context

    def _scope(self, crop: str) -> tuple[str, str]:
        definition = fs.load_definition(crop)
        return definition["country"], crop

    def options(self, crop: str, list_key: str) -> set[str]:
        country, crop_ = self._scope(crop)
        key = (list_key, country, crop_)
        if key not in self._options:
            rows = self.master.options(list_key, country=country, crop=crop_)
            self._options[key] = {r.value for r in rows}
            self._labels[key] = {r.value: r.label for r in rows}
        return self._options[key]

    def label(self, crop: str, list_key: str, value: str) -> str:
        self.options(crop, list_key)
        country, crop_ = self._scope(crop)
        return self._labels[(list_key, country, crop_)].get(value, value)

    def defaults(self, ctx: _BookContext) -> dict[str, Any]:
        return {
            "field.area_acre": round(ctx.field.area_acre, 2),
            "field.area_ha": round(ctx.field.area_ha, 2),
            "farmer.licence": ctx.farmer.home_office_licence_no,
            "season.variety": ctx.season.variety if ctx.season else None,
            "season.previous_crop": ctx.season.previous_crop if ctx.season else None,
        }

    def _validation_context(
        self, ctx: _BookContext, *, step_key: str | None = None, exclude_index: int | None = None
    ) -> fs.ValidationContext:
        single: dict[str, dict[str, Any]] = {}
        repeatable = {s["key"] for s in ctx.definition["steps"] if s["repeatable"]}
        siblings: list[dict[str, Any]] = []
        for entry in ctx.entries:
            if entry.step_key not in repeatable:
                single[entry.step_key] = entry.data
            elif entry.step_key == step_key and entry.entry_index != exclude_index:
                siblings.append(entry.data)
        return fs.ValidationContext(
            today=today(),
            options=lambda key: self.options(ctx.book.crop, key),
            values=self.defaults(ctx),
            single_steps=single,
            sibling_entries=siblings,
            sowing_ref=ctx.definition["sowing_date_ref"],
        )

    # ------------------------------------------------------------ book state

    def _issues(self, ctx: _BookContext) -> tuple[list[IssueOut], list[IssueOut]]:
        """Re-validate every saved entry against the book as it now stands."""
        warnings: list[IssueOut] = []
        errors: list[IssueOut] = []
        steps = {s["key"]: s for s in ctx.definition["steps"]}
        for entry in ctx.entries:
            step = steps.get(entry.step_key)
            if step is None:
                continue
            vctx = self._validation_context(
                ctx, step_key=entry.step_key, exclude_index=entry.entry_index
            )
            result = fs.validate_entry(step, entry.data, vctx)
            for issue in result.warnings:
                warnings.append(
                    IssueOut(
                        step_key=entry.step_key,
                        entry_index=entry.entry_index,
                        field=issue.field,
                        level="warning",
                        message=issue.message,
                    )
                )
            for issue in result.errors:
                errors.append(
                    IssueOut(
                        step_key=entry.step_key,
                        entry_index=entry.entry_index,
                        field=issue.field,
                        level="error",
                        message=issue.message,
                    )
                )
        return warnings, errors

    def _missing_steps(self, ctx: _BookContext) -> list[str]:
        """Steps that stop a submit: required and not done, or never answered."""
        statuses = self.statuses.for_book(ctx.book.id)
        counts: dict[str, int] = {}
        for entry in ctx.entries:
            counts[entry.step_key] = counts.get(entry.step_key, 0) + 1
        missing: list[str] = []
        for step in ctx.definition["steps"]:
            key = step["key"]
            status = statuses[key].status if key in statuses else STEP_NOT_STARTED
            has_entries = counts.get(key, 0) > 0
            if step.get("allow_not_applicable"):
                # Must be answered either way, so an omission is never silent.
                if not has_entries and status != STEP_NOT_APPLICABLE:
                    missing.append(key)
            elif step["required"] and not has_entries:
                missing.append(key)
        return missing

    def _clock(self, crop: str) -> clocks.Clock:
        row = self.clocks.for_crop(crop)
        if row is None:
            approach, ready, end = clocks.DEFAULT_CLOCKS[crop]
            return clocks.Clock(crop, approach, ready, end)
        return clocks.Clock(crop, row.approach_day, row.ready_day, row.window_end_day)

    def _status(self, ctx: _BookContext) -> clocks.CropStatus:
        vctx = self._validation_context(ctx)
        harvest = ctx.definition["harvest_step"]
        harvested = any(e.step_key == harvest for e in ctx.entries)
        return clocks.crop_status(
            self._clock(ctx.book.crop), vctx.sowing_date(), today(), harvested=harvested
        )

    def _photo_out(self, photo: FieldbookPhoto) -> PhotoOut:
        base = f"{meta.API_PREFIX}/books/{photo.fieldbook_id}/photos/{photo.id}"
        return PhotoOut(
            id=photo.id,
            original_name=photo.original_name,
            mime=photo.mime,
            size_bytes=photo.size_bytes,
            width=photo.width,
            height=photo.height,
            uploaded_at=photo.uploaded_at,
            url=base,
            thumb_url=f"{base}?size=thumb",
        )

    def state(self, ctx: _BookContext) -> BookOut:
        ctx.entries = self.entries.for_book(ctx.book.id)
        statuses = self.statuses.for_book(ctx.book.id)
        by_step: dict[str, list[FieldbookEntry]] = {}
        for entry in ctx.entries:
            by_step.setdefault(entry.step_key, []).append(entry)
        steps = [
            StepStateOut(
                key=s["key"],
                status=statuses[s["key"]].status if s["key"] in statuses else STEP_NOT_STARTED,
                entry_count=len(by_step.get(s["key"], [])),
                entries=[
                    EntryOut(
                        entry_index=e.entry_index,
                        data=e.data,
                        completed=e.completed,
                        updated_at=e.updated_at,
                        updated_by=e.updated_by,
                    )
                    for e in by_step.get(s["key"], [])
                ],
            )
            for s in ctx.definition["steps"]
        ]
        warnings, errors = self._issues(ctx)
        clock = self._clock(ctx.book.crop)
        status = self._status(ctx)
        book, farmer, field = ctx.book, ctx.farmer, ctx.field
        return BookOut(
            id=book.id,
            field_id=book.field_id,
            field_code=book.field_code,
            farmer_id=book.farmer_id,
            crop=book.crop,  # type: ignore[arg-type]
            season_year=book.season_year,
            status=book.status,  # type: ignore[arg-type]
            locked=book.locked,
            current_step=book.current_step,
            schema_version=book.schema_version,
            version=book.version,
            created_at=book.created_at,
            updated_at=book.updated_at,
            created_by=book.created_by,
            submitted_at=book.submitted_at,
            submitted_by=book.submitted_by,
            ready_for_pickup_at=book.ready_for_pickup_at,
            farmer=FarmerCardOut(
                id=farmer.id,
                sawie_id=farmer.sawie_id,
                name=farmer.name,
                crop=farmer.crop,
                country=farmer.country,
                registered_by=farmer.registered_by,
                home_office_licence_no=farmer.home_office_licence_no,
            ),
            field=FieldCardOut(
                id=field.id,
                field_id=field.field_id,
                area_acre=round(field.area_acre, 4),
                area_ha=round(field.area_ha, 4),
            ),
            defaults=self.defaults(ctx),
            steps=steps,
            photos=[self._photo_out(p) for p in self.photos.for_book(book.id)],
            warnings=warnings,
            errors=errors,
            missing_steps=self._missing_steps(ctx),
            crop_clock=CropClockOut(
                crop=clock.crop,
                approach_day=clock.approach_day,
                ready_day=clock.ready_day,
                window_end_day=clock.window_end_day,
            ),
            crop_status=CropStatusOut(
                status=status.status,
                label=status.label,
                days_after_sowing=status.days_after_sowing,
                sowing_date=status.sowing_date,
                overdue=status.overdue,
                next_milestone=status.next_milestone,
            ),
        )

    # ------------------------------------------------------------- reading

    def get(self, book_id: str, officer: CurrentOfficer) -> BookOut:
        return self.state(self._load(book_id, officer))

    def list_books(
        self,
        params: PageParams,
        officer: CurrentOfficer,
        *,
        season_year: int | None = None,
        status: str | None = None,
        crop: str | None = None,
        farmer_id: str | None = None,
    ) -> Page[BookListItemOut]:
        if officer.role in SEES_ALL_ROLES:
            farmer_ids: list[str] | None = None
        else:
            farmer_ids = [f.id for f in registry.list_farmers_for_officer(self.session, officer.id)]
        if farmer_id:
            farmer_ids = [farmer_id] if farmer_ids is None or farmer_id in farmer_ids else []
        result = self.books.search(
            params, farmer_ids=farmer_ids, season_year=season_year, status=status, crop=crop
        )
        return Page(
            items=[
                BookListItemOut(
                    id=b.id,
                    field_id=b.field_id,
                    field_code=b.field_code,
                    farmer_id=b.farmer_id,
                    crop=b.crop,
                    season_year=b.season_year,
                    status=b.status,
                    locked=b.locked,
                    updated_at=b.updated_at,
                )
                for b in result.rows
            ],
            total=result.total,
            page=params.page,
            page_size=params.page_size,
        )

    # ------------------------------------------------------------- opening

    def open(
        self, field_id: str, season_year: int, officer: CurrentOfficer, *, crop: str | None = None
    ) -> tuple[BookOut, bool]:
        """Create the draft, or return the existing fieldbook. ``(book, created)``."""
        field = registry.get_field(self.session, field_id)
        if field is None:
            raise NotFoundError(
                "That field does not exist.", code="field_not_found", details={"field_id": field_id}
            )
        farmer = registry.get_farmer(self.session, field.farmer_id)
        if farmer is None:
            raise NotFoundError("That farmer does not exist.", code="farmer_not_found")
        self._require_farmer_access(farmer, officer)
        if crop is not None and crop != farmer.crop:
            raise ConflictError(
                f"This farmer is in the {farmer.crop} programme, so their fieldbook uses the "
                f"{farmer.crop} forms.",
                code="fieldbook_crop_mismatch",
                details={"farmer_crop": farmer.crop, "sent_crop": crop},
            )

        existing = self.books.for_field(field.id, season_year)
        if existing is not None and existing.deleted_at is None:
            return self.get(existing.id, officer), False
        if existing is not None:
            # A removed draft keeps its row (unique per field and season); bring it back.
            self.session.delete(existing)
            self.session.flush()

        definition = fs.load_definition(farmer.crop)
        book = Fieldbook(
            field_id=field.id,
            field_code=field.field_id,
            farmer_id=farmer.id,
            crop=farmer.crop,
            season_year=season_year,
            status=STATUS_DRAFT,
            current_step=definition["steps"][0]["key"],
            schema_version=definition["version"],
            version=1,
            created_by=officer.id,
            updated_by=officer.id,
        )
        self.books.add(book)
        audit.record(
            "fieldbook",
            book.id,
            audit.ACTION_CREATE,
            officer.id,
            {
                "field_id": {"from": None, "to": field.field_id},
                "season_year": {"from": None, "to": season_year},
            },
            session=self.session,
        )
        self.session.commit()
        return self.get(book.id, officer), True

    # -------------------------------------------------------------- saving

    def _touch(self, ctx: _BookContext, officer: CurrentOfficer, step_key: str) -> None:
        book = ctx.book
        book.version += 1
        book.updated_by = officer.id
        book.updated_at = utcnow()
        keys = [s["key"] for s in ctx.definition["steps"]]
        index = keys.index(step_key)
        book.current_step = keys[min(index + 1, len(keys) - 1)]

    def _validate(
        self, ctx: _BookContext, step: dict[str, Any], data: dict[str, Any], index: int | None
    ) -> fs.EntryResult:
        vctx = self._validation_context(ctx, step_key=step["key"], exclude_index=index)
        result = fs.validate_entry(step, data, vctx)
        if not result.ok:
            raise ValidationAppError(
                "Some answers need fixing before this step can be saved.",
                details={
                    "fields": [
                        {
                            "field": i.field,
                            "location": "body",
                            "message": i.message,
                            "type": "schema",
                        }
                        for i in result.errors
                    ]
                },
            )
        return result

    def _write_entry(
        self,
        ctx: _BookContext,
        step: dict[str, Any],
        index: int,
        clean: dict[str, Any],
        officer: CurrentOfficer,
    ) -> FieldbookEntry:
        existing = self.entries.get_entry(ctx.book.id, step["key"], index)
        before = dict(existing.data) if existing else None
        if existing is None:
            entry = FieldbookEntry(
                fieldbook_id=ctx.book.id,
                step_key=step["key"],
                entry_index=index,
                data=clean,
                completed=True,
                updated_by=officer.id,
            )
            self.entries.add(entry)
            action = audit.ACTION_CREATE
        else:
            existing.data = clean
            existing.completed = True
            existing.updated_by = officer.id
            existing.updated_at = utcnow()
            entry = existing
            self.session.flush()
            action = audit.ACTION_UPDATE
        audit.record(
            "fieldbook_entry",
            entry.id,
            action,
            officer.id,
            audit.compute_diff(before, clean) | {"step_key": {"from": None, "to": step["key"]}},
            session=self.session,
        )
        self.statuses.set(ctx.book.id, step["key"], STEP_COMPLETE, officer.id)
        self._touch(ctx, officer, step["key"])
        self.bus.publish(
            events.FIELDBOOK_STEP_SAVED,
            {
                "fieldbook_id": ctx.book.id,
                "field_id": ctx.book.field_id,
                "season_year": ctx.book.season_year,
                "step_key": step["key"],
                "entry_index": index,
            },
            officer_id=officer.id,
            session=self.session,
        )
        self._maybe_ready_for_pickup(ctx, step, index, before, clean, officer)
        return entry

    def _maybe_ready_for_pickup(
        self,
        ctx: _BookContext,
        step: dict[str, Any],
        index: int,
        before: dict[str, Any] | None,
        clean: dict[str, Any],
        officer: CurrentOfficer,
    ) -> None:
        """Fire ``fieldbook.ready_for_pickup`` when an entry turns to "ready" (not on re-saves)."""
        pickup = ctx.definition["pickup"]
        if step["key"] != pickup["step"]:
            return
        if clean.get(pickup["field"]) != YES or (before or {}).get(pickup["field"]) == YES:
            return
        now = utcnow()
        if ctx.book.ready_for_pickup_at is None:
            ctx.book.ready_for_pickup_at = now
        label_field = pickup.get("label_field")
        picking = clean.get(label_field) if label_field else index + 1
        self.bus.publish(
            events.FIELDBOOK_READY_FOR_PICKUP,
            {
                "fieldbook_id": ctx.book.id,
                "field_id": ctx.book.field_id,
                "farmer_id": ctx.book.farmer_id,
                "season_year": ctx.book.season_year,
                "picking_number": picking,
                "entry_index": index,
                "crop": ctx.book.crop,
                "estimated_kg": self._entry_kg(ctx, clean),
                "ready_at": now.isoformat(),
            },
            officer_id=officer.id,
            session=self.session,
        )

    def _entry_kg(self, ctx: _BookContext, data: dict[str, Any]) -> float | None:
        if ctx.book.crop == "cotton":
            area = (self._validation_context(ctx).single_steps.get("field_info") or {}).get(
                "area_sown"
            )
            if data.get("yield") is None or area is None:
                return None
            return round(float(data["yield"]) * float(area) * 40.0, 1)
        weight = data.get("total_straw_weight")
        return float(weight) if weight is not None else None

    def _result(
        self, ctx: _BookContext, result: fs.EntryResult, step_key: str, index: int
    ) -> SaveResultOut:
        self.session.commit()
        return SaveResultOut(
            book=self.state(ctx),
            warnings=[
                IssueOut(
                    step_key=step_key,
                    entry_index=index,
                    field=w.field,
                    level="warning",
                    message=w.message,
                )
                for w in result.warnings
            ],
        )

    def save_single(
        self,
        book_id: str,
        step_key: str,
        payload: EntryIn,
        officer: CurrentOfficer,
        *,
        version: int | None,
    ) -> SaveResultOut:
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version, crop=payload.crop)
        step = fs.get_step(ctx.definition, step_key)
        if step["repeatable"]:
            raise ConflictError(
                f"'{step['title']}' takes several entries; add them one by one.",
                code="fieldbook_step_repeatable",
            )
        result = self._validate(ctx, step, payload.data, 0)
        self._write_entry(ctx, step, 0, result.clean, officer)
        return self._result(ctx, result, step_key, 0)

    def save_entry(
        self,
        book_id: str,
        step_key: str,
        payload: EntryIn,
        officer: CurrentOfficer,
        *,
        version: int | None,
        index: int | None = None,
    ) -> SaveResultOut:
        """Add an entry (``index`` None) or replace one, in a repeatable step."""
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version, crop=payload.crop)
        step = fs.get_step(ctx.definition, step_key)
        if not step["repeatable"]:
            raise ConflictError(
                f"'{step['title']}' has a single entry; save the step instead.",
                code="fieldbook_step_single",
            )
        if index is not None and self.entries.get_entry(ctx.book.id, step_key, index) is None:
            raise NotFoundError(
                "That entry does not exist.",
                code="fieldbook_entry_not_found",
                details={"step_key": step_key, "entry_index": index},
            )
        target = index if index is not None else self.entries.next_index(ctx.book.id, step_key)
        result = self._validate(ctx, step, payload.data, target)
        self._write_entry(ctx, step, target, result.clean, officer)
        return self._result(ctx, result, step_key, target)

    def delete_entry(
        self,
        book_id: str,
        step_key: str,
        index: int,
        officer: CurrentOfficer,
        *,
        version: int | None,
    ) -> BookOut:
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version)
        step = fs.get_step(ctx.definition, step_key)
        entry = self.entries.get_entry(ctx.book.id, step_key, index)
        if entry is None:
            raise NotFoundError("That entry does not exist.", code="fieldbook_entry_not_found")
        audit.record(
            "fieldbook_entry",
            entry.id,
            audit.ACTION_DELETE,
            officer.id,
            audit.compute_diff(entry.data, None),
            session=self.session,
        )
        self.entries.delete(entry)
        remaining = self.entries.for_step(ctx.book.id, step_key)
        self.statuses.set(
            ctx.book.id, step_key, STEP_COMPLETE if remaining else STEP_NOT_STARTED, officer.id
        )
        self._touch(ctx, officer, step["key"])
        ctx.book.current_step = step_key
        self.session.commit()
        return self.state(ctx)

    def set_not_applicable(
        self,
        book_id: str,
        step_key: str,
        value: bool,
        officer: CurrentOfficer,
        *,
        version: int | None,
        crop: str | None = None,
    ) -> BookOut:
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version, crop=crop)
        step = fs.get_step(ctx.definition, step_key)
        if not step.get("allow_not_applicable"):
            raise ConflictError(
                f"'{step['title']}' must be recorded; it cannot be marked not applicable.",
                code="fieldbook_step_required",
            )
        if value and self.entries.for_step(ctx.book.id, step_key):
            raise ConflictError(
                "Delete this step's entries before marking it not applicable.",
                code="fieldbook_step_has_entries",
            )
        self.statuses.set(
            ctx.book.id, step_key, STEP_NOT_APPLICABLE if value else STEP_NOT_STARTED, officer.id
        )
        audit.record(
            "fieldbook",
            ctx.book.id,
            audit.ACTION_STATE_CHANGE,
            officer.id,
            {f"{step_key}.not_applicable": {"from": not value, "to": value}},
            session=self.session,
        )
        self._touch(ctx, officer, step_key)
        self.session.commit()
        return self.state(ctx)

    # ---------------------------------------------------------------- photos

    def add_photos(
        self,
        book_id: str,
        files: Sequence[tuple[str, bytes]],
        officer: CurrentOfficer,
        *,
        version: int | None,
    ) -> BookOut:
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version)
        if not files:
            raise ValidationAppError("Choose at least one photo.", code="photo_missing")
        if self.photos.count_for_book(ctx.book.id) + len(files) > photo_store.MAX_PHOTOS:
            raise ConflictError(
                f"A fieldbook holds at most {photo_store.MAX_PHOTOS} photos.",
                code="photo_limit",
                details={"limit": photo_store.MAX_PHOTOS},
            )
        written: list[str] = []
        try:
            for name, content in files:
                stored = photo_store.store_photo(self.upload_root, ctx.book.id, content, name)
                written += [stored.file_path, stored.thumb_path]
                photo = FieldbookPhoto(
                    fieldbook_id=ctx.book.id,
                    file_path=stored.file_path,
                    thumb_path=stored.thumb_path,
                    original_name=name[:255],
                    mime=stored.mime,
                    size_bytes=stored.size_bytes,
                    width=stored.width,
                    height=stored.height,
                    uploaded_by=officer.id,
                )
                self.photos.add(photo)
                audit.record(
                    "fieldbook_photo",
                    photo.id,
                    audit.ACTION_CREATE,
                    officer.id,
                    {"name": {"from": None, "to": name}},
                    session=self.session,
                )
        except Exception:
            # One bad file rejects the batch; do not leave orphans on disk.
            photo_store.remove_files(self.upload_root, *written)
            raise
        self._touch(ctx, officer, ctx.definition["steps"][0]["key"])
        ctx.book.current_step = ctx.definition["steps"][0]["key"]
        self.session.commit()
        return self.state(ctx)

    def delete_photo(
        self, book_id: str, photo_id: str, officer: CurrentOfficer, *, version: int | None
    ) -> BookOut:
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version)
        photo = self.photos.get(photo_id)
        if photo is None or photo.fieldbook_id != ctx.book.id:
            raise NotFoundError("That photo does not exist.", code="photo_not_found")
        paths = (photo.file_path, photo.thumb_path)
        audit.record(
            "fieldbook_photo",
            photo.id,
            audit.ACTION_DELETE,
            officer.id,
            {"name": {"from": photo.original_name, "to": None}},
            session=self.session,
        )
        self.session.delete(photo)
        ctx.book.version += 1
        ctx.book.updated_by = officer.id
        self.session.commit()
        photo_store.remove_files(self.upload_root, *paths)
        return self.state(ctx)

    def photo_file(
        self, book_id: str, photo_id: str, officer: CurrentOfficer, *, thumb: bool
    ) -> tuple[Path, str]:
        ctx = self._load(book_id, officer)
        photo = self.photos.get(photo_id)
        if photo is None or photo.fieldbook_id != ctx.book.id:
            raise NotFoundError("That photo does not exist.", code="photo_not_found")
        rel = photo.thumb_path if thumb else photo.file_path
        return self.upload_root / rel, "image/jpeg" if thumb else photo.mime

    # ---------------------------------------------------------------- submit

    def submit(self, book_id: str, officer: CurrentOfficer, *, version: int | None) -> BookOut:
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version)
        missing = self._missing_steps(ctx)
        if missing:
            titles = {s["key"]: s["title"] for s in ctx.definition["steps"]}
            raise ConflictError(
                "Some steps are not finished: " + ", ".join(titles[k] for k in missing) + ".",
                code="fieldbook_incomplete",
                details={"missing_steps": missing},
            )
        _, errors = self._issues(ctx)
        if errors:
            raise ConflictError(
                "Some saved answers now conflict with other steps. Fix them before submitting.",
                code="fieldbook_has_errors",
                details={"errors": [e.model_dump() for e in errors]},
            )
        book = ctx.book
        book.status = STATUS_SUBMITTED
        book.locked = True
        book.submitted_at = utcnow()
        book.submitted_by = officer.id
        book.version += 1
        book.updated_by = officer.id
        audit.record(
            "fieldbook",
            book.id,
            audit.ACTION_STATE_CHANGE,
            officer.id,
            {
                "status": {"from": STATUS_DRAFT, "to": STATUS_SUBMITTED},
                "locked": {"from": False, "to": True},
            },
            session=self.session,
        )
        self.bus.publish(
            events.FIELDBOOK_SUBMITTED,
            {
                "fieldbook_id": book.id,
                "field_id": book.field_id,
                "farmer_id": book.farmer_id,
                "season_year": book.season_year,
            },
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return self.state(ctx)

    # ---------------------------------------------------------------- delete

    def delete_book(self, book_id: str, officer: CurrentOfficer, *, version: int | None) -> None:
        ctx = self._load(book_id, officer)
        self._guard_write(ctx, version=version)
        if officer.role not in SEES_ALL_ROLES and ctx.book.created_by != officer.id:
            raise ForbiddenError(
                "Only the officer who created this draft, or an administrator, can delete it.",
                code="fieldbook_delete_forbidden",
            )
        book_id_ = ctx.book.id
        audit.record(
            "fieldbook",
            book_id_,
            audit.ACTION_DELETE,
            officer.id,
            {"status": {"from": ctx.book.status, "to": None}},
            session=self.session,
        )
        self.session.delete(ctx.book)
        self.session.commit()
        photo_store.remove_book_dir(self.upload_root, book_id_)

    # -------------------------------------------------------------- timeline

    def timeline(self, book_id: str, officer: CurrentOfficer) -> TimelineOut:
        ctx = self._load(book_id, officer)
        return TimelineOut(items=build_timeline(self, ctx.book, ctx.definition, ctx.entries))


def build_timeline(
    service: FieldbookService,
    book: Fieldbook,
    definition: dict[str, Any],
    entries: Sequence[FieldbookEntry],
) -> list[TimelineItemOut]:
    """Every saved entry, newest first, with a one-line summary and the officer."""
    steps = {s["key"]: s for s in definition["steps"]}
    names: dict[str, str | None] = {}

    def name(officer_id: str | None) -> str | None:
        if officer_id is None:
            return None
        if officer_id not in names:
            row = service.officers.get(officer_id)
            names[officer_id] = row.full_name if row else None
        return names[officer_id]

    def label(list_key: str, value: str) -> str:
        return service.label(book.crop, list_key, value)

    items: list[TimelineItemOut] = []
    for entry in entries:
        step = steps.get(entry.step_key)
        if step is None:
            continue
        items.append(
            TimelineItemOut(
                at=entry.updated_at,
                step_key=entry.step_key,
                step_title=step["title"],
                entry_index=entry.entry_index,
                kind="entry",
                summary=fs.summarise(step, entry.data, label),
                officer_id=entry.updated_by,
                officer_name=name(entry.updated_by),
            )
        )
    for key, status in service.statuses.for_book(book.id).items():
        if status.status == STEP_NOT_APPLICABLE and key in steps:
            items.append(
                TimelineItemOut(
                    at=status.updated_at,
                    step_key=key,
                    step_title=steps[key]["title"],
                    entry_index=None,
                    kind="not_applicable",
                    summary="Nothing to record",
                    officer_id=status.updated_by,
                    officer_name=name(status.updated_by),
                )
            )
    items.append(
        TimelineItemOut(
            at=book.created_at,
            step_key=None,
            step_title=None,
            entry_index=None,
            kind="created",
            summary=f"Fieldbook opened for {book.field_code}, season {book.season_year}",
            officer_id=book.created_by,
            officer_name=name(book.created_by),
        )
    )
    if book.submitted_at:
        items.append(
            TimelineItemOut(
                at=book.submitted_at,
                step_key=None,
                step_title=None,
                entry_index=None,
                kind="submitted",
                summary="Submitted and locked",
                officer_id=book.submitted_by,
                officer_name=name(book.submitted_by),
            )
        )
    items.sort(key=lambda i: i.at, reverse=True)
    return items
