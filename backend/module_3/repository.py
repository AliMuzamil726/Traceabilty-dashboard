"""Data access for Module 3. The only layer that builds SQL for this module's tables."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from core.pagination import PageParams, PageResult, paginate
from module_3.models import (
    STATUS_SUBMITTED,
    CropClockConfig,
    Fieldbook,
    FieldbookEntry,
    FieldbookPhoto,
    FieldbookStepStatus,
)
from shared.repositories.base import BaseRepository

#: Rows per IN (...) list, well inside SQLite's bound-parameter limit.
CHUNK = 500


def _chunks(items: list[str]) -> list[list[str]]:
    return [items[i : i + CHUNK] for i in range(0, len(items), CHUNK)]


class FieldbookRepository(BaseRepository[Fieldbook]):
    model = Fieldbook

    def get_active(self, fieldbook_id: str) -> Fieldbook | None:
        stmt = select(Fieldbook).where(Fieldbook.id == fieldbook_id, Fieldbook.deleted_at.is_(None))
        return self.session.execute(stmt).scalars().first()

    def for_field(self, field_id: str, season_year: int) -> Fieldbook | None:
        """The fieldbook of one field and season, including a soft-removed one."""
        stmt = select(Fieldbook).where(
            Fieldbook.field_id == field_id, Fieldbook.season_year == season_year
        )
        return self.session.execute(stmt).scalars().first()

    def active_for_fields(self, field_ids: Sequence[str], season_year: int) -> dict[str, Fieldbook]:
        if not field_ids:
            return {}
        stmt = select(Fieldbook).where(
            Fieldbook.field_id.in_(list(field_ids)),
            Fieldbook.season_year == season_year,
            Fieldbook.deleted_at.is_(None),
        )
        return {b.field_id: b for b in self.session.execute(stmt).scalars().all()}

    def active_for_pairs(
        self, pairs: Sequence[tuple[str, int]]
    ) -> dict[tuple[str, int], Fieldbook]:
        """Active books for many (field_id, season_year) pairs, in one query per chunk."""
        wanted = {(f, int(y)) for f, y in pairs}
        if not wanted:
            return {}
        out: dict[tuple[str, int], Fieldbook] = {}
        field_ids = sorted({f for f, _ in wanted})
        years = sorted({y for _, y in wanted})
        for chunk in _chunks(field_ids):
            stmt = select(Fieldbook).where(
                Fieldbook.field_id.in_(chunk),
                Fieldbook.season_year.in_(years),
                Fieldbook.deleted_at.is_(None),
            )
            for book in self.session.execute(stmt).scalars():
                key = (book.field_id, book.season_year)
                if key in wanted:
                    out[key] = book
        return out

    def drafts_for_field(self, field_id: str) -> list[Fieldbook]:
        stmt = select(Fieldbook).where(
            Fieldbook.field_id == field_id,
            Fieldbook.status != STATUS_SUBMITTED,
            Fieldbook.deleted_at.is_(None),
        )
        return list(self.session.execute(stmt).scalars().all())

    def has_submitted(self, field_id: str) -> bool:
        stmt = (
            select(Fieldbook.id)
            .where(Fieldbook.field_id == field_id, Fieldbook.status == STATUS_SUBMITTED)
            .limit(1)
        )
        return self.session.execute(stmt).first() is not None

    def search(
        self,
        params: PageParams,
        *,
        farmer_ids: Sequence[str] | None = None,
        season_year: int | None = None,
        status: str | None = None,
        crop: str | None = None,
    ) -> PageResult[Fieldbook]:
        stmt = select(Fieldbook).where(Fieldbook.deleted_at.is_(None))
        if farmer_ids is not None:
            stmt = stmt.where(Fieldbook.farmer_id.in_(list(farmer_ids)))
        if season_year:
            stmt = stmt.where(Fieldbook.season_year == season_year)
        if status:
            stmt = stmt.where(Fieldbook.status == status)
        if crop:
            stmt = stmt.where(Fieldbook.crop == crop)
        stmt = stmt.order_by(Fieldbook.updated_at.desc())
        return paginate(self.session, stmt, params)

    # ----------------------------------------------------- aggregates (Dashboard)

    def count_by_status(
        self, *, crop: str | None = None, season_year: int | None = None
    ) -> dict[str, int]:
        """Live fieldbooks per status (``draft``, ``submitted``) in one query."""
        stmt = (
            select(Fieldbook.status, func.count())
            .where(Fieldbook.deleted_at.is_(None))
            .group_by(Fieldbook.status)
        )
        if crop:
            stmt = stmt.where(Fieldbook.crop == crop)
        if season_year:
            stmt = stmt.where(Fieldbook.season_year == season_year)
        return {row[0]: int(row[1]) for row in self.session.execute(stmt).all()}

    def count_submitted_by_officer(
        self, *, crop: str | None = None, season_year: int | None = None
    ) -> dict[str, int]:
        """Submitted fieldbooks per submitting officer, in one query."""
        stmt = (
            select(Fieldbook.submitted_by, func.count())
            .where(Fieldbook.deleted_at.is_(None), Fieldbook.status == STATUS_SUBMITTED)
            .group_by(Fieldbook.submitted_by)
        )
        if crop:
            stmt = stmt.where(Fieldbook.crop == crop)
        if season_year:
            stmt = stmt.where(Fieldbook.season_year == season_year)
        return {row[0]: int(row[1]) for row in self.session.execute(stmt).all() if row[0]}

    def stale_drafts(
        self,
        *,
        updated_before: datetime,
        crop: str | None = None,
        season_year: int | None = None,
    ) -> list[Any]:
        """Drafts nobody has touched since ``updated_before``, oldest first.

        Only the columns a listing needs are selected, not whole fieldbooks: the
        Dashboard can face thousands of forgotten drafts and hydrating each one as an
        ORM object is most of the cost of counting them (D-096).
        """
        stmt = select(
            Fieldbook.id,
            Fieldbook.field_id,
            Fieldbook.field_code,
            Fieldbook.farmer_id,
            Fieldbook.crop,
            Fieldbook.season_year,
            Fieldbook.updated_at,
        ).where(
            Fieldbook.deleted_at.is_(None),
            Fieldbook.status != STATUS_SUBMITTED,
            Fieldbook.updated_at < updated_before,
        )
        if crop:
            stmt = stmt.where(Fieldbook.crop == crop)
        if season_year:
            stmt = stmt.where(Fieldbook.season_year == season_year)
        return list(self.session.execute(stmt.order_by(Fieldbook.updated_at)).all())

    def refs_for_crop_season(self, *, crop: str, season_year: int | None = None) -> list[Any]:
        """Identity columns of every live fieldbook of a crop and season.

        Columns rather than entities, for the same reason as :meth:`stale_drafts`.
        """
        stmt = select(
            Fieldbook.id,
            Fieldbook.field_id,
            Fieldbook.field_code,
            Fieldbook.farmer_id,
            Fieldbook.season_year,
        ).where(Fieldbook.deleted_at.is_(None), Fieldbook.crop == crop)
        if season_year:
            stmt = stmt.where(Fieldbook.season_year == season_year)
        return list(self.session.execute(stmt.order_by(Fieldbook.field_code)).all())

    def with_pickup(
        self, *, crop: str | None = None, season_year: int | None = None
    ) -> list[Fieldbook]:
        stmt = select(Fieldbook).where(
            Fieldbook.deleted_at.is_(None), Fieldbook.ready_for_pickup_at.is_not(None)
        )
        if crop:
            stmt = stmt.where(Fieldbook.crop == crop)
        if season_year:
            stmt = stmt.where(Fieldbook.season_year == season_year)
        return list(self.session.execute(stmt).scalars().all())


class EntryRepository(BaseRepository[FieldbookEntry]):
    model = FieldbookEntry

    def for_book(self, fieldbook_id: str) -> list[FieldbookEntry]:
        stmt = (
            select(FieldbookEntry)
            .where(FieldbookEntry.fieldbook_id == fieldbook_id)
            .order_by(FieldbookEntry.step_key, FieldbookEntry.entry_index)
        )
        return list(self.session.execute(stmt).scalars().all())

    def for_books(self, fieldbook_ids: Sequence[str]) -> dict[str, list[FieldbookEntry]]:
        """Every entry of many books, grouped by book, in one query per chunk."""
        out: dict[str, list[FieldbookEntry]] = {i: [] for i in fieldbook_ids}
        for chunk in _chunks(list(fieldbook_ids)):
            stmt = (
                select(FieldbookEntry)
                .where(FieldbookEntry.fieldbook_id.in_(chunk))
                .order_by(FieldbookEntry.step_key, FieldbookEntry.entry_index)
            )
            for entry in self.session.execute(stmt).scalars():
                out[entry.fieldbook_id].append(entry)
        return out

    def step_data_for_books(
        self, fieldbook_ids: Sequence[str], step_key: str
    ) -> dict[str, dict[str, Any]]:
        """One step's entry for many fieldbooks, in one query per chunk.

        Added for Module 1 (D-096): the licence alert reads one step of every hemp
        fieldbook, and loading every entry of every book to find it is wasteful.
        """
        ids = [i for i in fieldbook_ids if i]
        out: dict[str, dict[str, Any]] = {}
        for chunk in _chunks(ids):
            stmt = select(FieldbookEntry.fieldbook_id, FieldbookEntry.data).where(
                FieldbookEntry.fieldbook_id.in_(chunk),
                FieldbookEntry.step_key == step_key,
                FieldbookEntry.entry_index == 0,
            )
            for row in self.session.execute(stmt).all():
                out[row[0]] = row[1]
        return out

    def for_step(self, fieldbook_id: str, step_key: str) -> list[FieldbookEntry]:
        stmt = (
            select(FieldbookEntry)
            .where(FieldbookEntry.fieldbook_id == fieldbook_id, FieldbookEntry.step_key == step_key)
            .order_by(FieldbookEntry.entry_index)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_entry(self, fieldbook_id: str, step_key: str, index: int) -> FieldbookEntry | None:
        return self.find_one_by(fieldbook_id=fieldbook_id, step_key=step_key, entry_index=index)

    def next_index(self, fieldbook_id: str, step_key: str) -> int:
        stmt = select(func.max(FieldbookEntry.entry_index)).where(
            FieldbookEntry.fieldbook_id == fieldbook_id, FieldbookEntry.step_key == step_key
        )
        current = self.session.execute(stmt).scalar()
        return 0 if current is None else int(current) + 1

    def delete(self, entry: FieldbookEntry) -> None:
        self.session.delete(entry)
        self.session.flush()


class StepStatusRepository(BaseRepository[FieldbookStepStatus]):
    model = FieldbookStepStatus

    def for_book(self, fieldbook_id: str) -> dict[str, FieldbookStepStatus]:
        stmt = select(FieldbookStepStatus).where(FieldbookStepStatus.fieldbook_id == fieldbook_id)
        return {s.step_key: s for s in self.session.execute(stmt).scalars().all()}

    def count_done_by_book(
        self, fieldbook_ids: Sequence[str], *, statuses: Sequence[str]
    ) -> dict[str, int]:
        """How many steps each of these fieldbooks has finished. One query per chunk.

        Added for Module 1's attention panel (D-096): reading the statuses book by book
        would be one query per draft, which is the N+1 the dashboard must never do.
        """
        ids = [i for i in fieldbook_ids if i]
        if not ids:
            return {}
        out: dict[str, int] = {}
        for chunk in _chunks(ids):
            stmt = (
                select(FieldbookStepStatus.fieldbook_id, func.count())
                .where(
                    FieldbookStepStatus.fieldbook_id.in_(chunk),
                    FieldbookStepStatus.status.in_(list(statuses)),
                )
                .group_by(FieldbookStepStatus.fieldbook_id)
            )
            for row in self.session.execute(stmt).all():
                out[row[0]] = out.get(row[0], 0) + int(row[1])
        return out

    def count_done_by_step(
        self, *, crop: str, season_year: int | None = None, statuses: Sequence[str]
    ) -> dict[str, int]:
        """How many live fieldbooks of this crop have each step finished. One query.

        Added for Module 1's completion funnel (D-096). ``statuses`` is the set that
        counts as finished, which the caller takes from Module 3's own step statuses.
        """
        stmt = (
            select(FieldbookStepStatus.step_key, func.count())
            .join(Fieldbook, Fieldbook.id == FieldbookStepStatus.fieldbook_id)
            .where(
                Fieldbook.deleted_at.is_(None),
                Fieldbook.crop == crop,
                FieldbookStepStatus.status.in_(list(statuses)),
            )
            .group_by(FieldbookStepStatus.step_key)
        )
        if season_year:
            stmt = stmt.where(Fieldbook.season_year == season_year)
        return {row[0]: int(row[1]) for row in self.session.execute(stmt).all()}

    def set(self, fieldbook_id: str, step_key: str, status: str, officer_id: str | None) -> None:
        row = self.session.get(FieldbookStepStatus, (fieldbook_id, step_key))
        if row is None:
            self.add(
                FieldbookStepStatus(
                    fieldbook_id=fieldbook_id,
                    step_key=step_key,
                    status=status,
                    updated_by=officer_id,
                )
            )
        else:
            row.status = status
            row.updated_by = officer_id
            self.session.flush()


class PhotoRepository(BaseRepository[FieldbookPhoto]):
    model = FieldbookPhoto

    def for_book(self, fieldbook_id: str) -> list[FieldbookPhoto]:
        stmt = (
            select(FieldbookPhoto)
            .where(FieldbookPhoto.fieldbook_id == fieldbook_id)
            .order_by(FieldbookPhoto.uploaded_at)
        )
        return list(self.session.execute(stmt).scalars().all())

    def count_for_book(self, fieldbook_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(FieldbookPhoto)
            .where(FieldbookPhoto.fieldbook_id == fieldbook_id)
        )
        return int(self.session.execute(stmt).scalar_one())


class CropClockRepository(BaseRepository[CropClockConfig]):
    model = CropClockConfig

    def all(self) -> dict[str, CropClockConfig]:
        return {r.crop: r for r in self.session.execute(select(CropClockConfig)).scalars()}

    def for_crop(self, crop: str) -> CropClockConfig | None:
        return self.find_one_by(crop=crop)


__all__ = [
    "CropClockRepository",
    "EntryRepository",
    "FieldbookRepository",
    "PhotoRepository",
    "StepStatusRepository",
]
