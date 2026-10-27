"""Data access for Module 6 (Heap). The only layer that builds SQL for its tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from module_6.models import BALE_ACTIVE, OPEN, Bale, Heap, HeapConfig
from shared.repositories.base import BaseRepository


class HeapRepository(BaseRepository[Heap]):
    model = Heap

    def get_for_update(self, heap_pk: str) -> Heap | None:
        stmt = select(Heap).where(Heap.id == heap_pk).with_for_update()
        return self.session.execute(stmt).scalars().first()

    def by_business_id(self, heap_id: str) -> Heap | None:
        return self.session.execute(select(Heap).where(Heap.heap_id == heap_id)).scalars().first()

    def resolve(self, key: str) -> Heap | None:
        """By primary key or by business ID."""
        return self.get(key) or self.by_business_id(key)

    def filtered(
        self, *, crop: str | None = None, site_id: str | None = None, status: str | None = None
    ) -> list[Heap]:
        stmt = select(Heap)
        if crop:
            stmt = stmt.where(Heap.crop == crop)
        if site_id:
            stmt = stmt.where(Heap.site_id == site_id)
        if status:
            stmt = stmt.where(Heap.status == status)
        return list(
            self.session.execute(
                stmt.order_by(Heap.opened_at.desc(), Heap.heap_id.desc())
            ).scalars()
        )

    def business_ids(self, *, crop: str | None = None, site_id: str | None = None) -> list[str]:
        """Just the business IDs, for a reader that needs to name heaps and nothing else.

        Added for Module 1 (D-096): the scan counts are filtered by crop, which means
        "the codes of that crop's heaps", and hydrating every heap to read one column
        of it is wasted work on a site with hundreds.
        """
        stmt = select(Heap.heap_id)
        if crop:
            stmt = stmt.where(Heap.crop == crop)
        if site_id:
            stmt = stmt.where(Heap.site_id == site_id)
        return list(self.session.execute(stmt.order_by(Heap.heap_id)).scalars().all())

    def open_at(self, site_id: str) -> list[Heap]:
        return self.filtered(site_id=site_id, status=OPEN)


class BaleRepository(BaseRepository[Bale]):
    model = Bale

    def for_heap(self, heap_pk: str) -> list[Bale]:
        stmt = select(Bale).where(Bale.heap_pk == heap_pk).order_by(Bale.seq)
        return list(self.session.execute(stmt).scalars())

    def active_count(self, heap_pk: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Bale)
            .where(Bale.heap_pk == heap_pk, Bale.status == BALE_ACTIVE)
        )
        return int(self.session.execute(stmt).scalar_one())

    def any_for_heap(self, heap_pk: str) -> bool:
        return (
            self.session.execute(select(Bale.id).where(Bale.heap_pk == heap_pk).limit(1)).first()
            is not None
        )

    def max_seq(self, heap_pk: str) -> int:
        stmt = select(func.max(Bale.seq)).where(Bale.heap_pk == heap_pk)
        return int(self.session.execute(stmt).scalar() or 0)

    def by_serial(self, serial: str) -> Bale | None:
        return (
            self.session.execute(select(Bale).where(Bale.bale_serial == serial)).scalars().first()
        )

    # ----------------------------------------------------- aggregates (Dashboard)

    def active_totals_by_heap(self) -> dict[str, tuple[int, float, datetime | None]]:
        """``{heap_pk: (active_bales, weight_kg, last_created_at)}`` in one query."""
        stmt = (
            select(
                Bale.heap_pk,
                func.count(),
                func.coalesce(func.sum(Bale.weight_kg), 0.0),
                func.max(Bale.created_at),
            )
            .where(Bale.status == BALE_ACTIVE)
            .group_by(Bale.heap_pk)
        )
        return {
            str(row[0]): (int(row[1]), round(float(row[2]), 1), row[3])
            for row in self.session.execute(stmt).all()
        }

    def count_active(
        self,
        *,
        crop: str | None = None,
        site_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """Active bales, optionally of one crop or site and made inside a time range."""
        stmt = (
            select(func.count())
            .select_from(Bale)
            .join(Heap, Heap.id == Bale.heap_pk)
            .where(Bale.status == BALE_ACTIVE)
        )
        if crop:
            stmt = stmt.where(Heap.crop == crop)
        if site_id:
            stmt = stmt.where(Heap.site_id == site_id)
        if since:
            stmt = stmt.where(Bale.created_at >= since)
        if until:
            stmt = stmt.where(Bale.created_at <= until)
        return int(self.session.execute(stmt).scalar_one())


class HeapConfigRepository(BaseRepository[HeapConfig]):
    model = HeapConfig

    def for_crop(self, crop: str) -> HeapConfig | None:
        return (
            self.session.execute(select(HeapConfig).where(HeapConfig.crop == crop))
            .scalars()
            .first()
        )
