"""Data access for Module 7 (QR Tracing). The only layer that builds SQL for its tables."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from module_7.models import ACTIVE, TYPE_BALE, TYPE_HEAP, QrScanLog, QrToken
from shared.repositories.base import BaseRepository

#: Ids per ``IN (...)`` list, well inside SQLite's bound-parameter limit.
CHUNK = 400


class TokenRepository(BaseRepository[QrToken]):
    model = QrToken

    def by_token(self, token: str) -> QrToken | None:
        return self.session.execute(select(QrToken).where(QrToken.token == token)).scalars().first()

    def exists(self, token: str) -> bool:
        return (
            self.session.execute(select(QrToken.id).where(QrToken.token == token)).first()
            is not None
        )

    def active_for_bale(self, serial: str) -> QrToken | None:
        stmt = select(QrToken).where(
            QrToken.token_type == TYPE_BALE, QrToken.bale_serial == serial, QrToken.status == ACTIVE
        )
        return self.session.execute(stmt).scalars().first()

    def latest_for_bale(self, serial: str) -> QrToken | None:
        stmt = (
            select(QrToken)
            .where(QrToken.token_type == TYPE_BALE, QrToken.bale_serial == serial)
            .order_by(QrToken.created_at.desc())
        )
        return self.session.execute(stmt).scalars().first()

    def active_for_heap(self, heap_id: str) -> QrToken | None:
        stmt = select(QrToken).where(
            QrToken.token_type == TYPE_HEAP, QrToken.heap_id == heap_id, QrToken.status == ACTIVE
        )
        return self.session.execute(stmt).scalars().first()

    def for_heap_bales(self, heap_id: str) -> list[QrToken]:
        stmt = (
            select(QrToken)
            .where(QrToken.token_type == TYPE_BALE, QrToken.heap_id == heap_id)
            .order_by(QrToken.bale_serial, QrToken.created_at)
        )
        return list(self.session.execute(stmt).scalars())

    def count_active(
        self, *, token_type: str | None = None, heap_ids: Sequence[str] | None = None
    ) -> int:
        stmt = select(func.count()).select_from(QrToken).where(QrToken.status == ACTIVE)
        if token_type:
            stmt = stmt.where(QrToken.token_type == token_type)
        if heap_ids is None:
            return int(self.session.execute(stmt).scalar_one())
        ids = list(heap_ids)
        batches = [ids[i : i + CHUNK] for i in range(0, len(ids), CHUNK)] or [[]]
        return sum(
            int(self.session.execute(stmt.where(QrToken.heap_id.in_(b or [""]))).scalar_one())
            for b in batches
        )


class ScanRepository(BaseRepository[QrScanLog]):
    model = QrScanLog

    def counts_by_token(self, token_ids: Sequence[str]) -> dict[str, int]:
        if not token_ids:
            return {}
        stmt = (
            select(QrScanLog.token_id, func.count())
            .where(QrScanLog.token_id.in_(list(token_ids)))
            .group_by(QrScanLog.token_id)
        )
        return {row[0]: int(row[1]) for row in self.session.execute(stmt)}

    def summary(self, token_ids: Sequence[str] | None = None) -> tuple[int, int, datetime | None]:
        """(total scans, public scans, last scan time)."""
        stmt = select(func.count(), func.max(QrScanLog.scanned_at))
        public = select(func.count()).select_from(QrScanLog).where(QrScanLog.channel == "public")
        if token_ids is not None:
            ids = list(token_ids) or [""]
            stmt = stmt.where(QrScanLog.token_id.in_(ids))
            public = public.where(QrScanLog.token_id.in_(ids))
        total, last = self.session.execute(stmt).one()
        return int(total or 0), int(self.session.execute(public).scalar_one()), last

    # ----------------------------------------------------- aggregates (Dashboard)

    def totals(
        self,
        *,
        heap_ids: Sequence[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[int, int, datetime | None]:
        """``(total, public, last_scan_at)`` for a set of heaps and a time range.

        Added for Module 1 (D-096). ``heap_ids=None`` counts every scan; an empty
        sequence counts none, which is what a crop with no codes yet means. The heaps
        are joined through the codes rather than resolved to code ids first, so the
        bound-parameter list stays the size of the heap set, not of every code.
        """
        batches: list[Sequence[str] | None] = [None]
        if heap_ids is not None:
            ids = list(heap_ids)
            batches = [ids[i : i + CHUNK] for i in range(0, len(ids), CHUNK)] or [[]]
        total = public = 0
        last: datetime | None = None
        for batch in batches:
            counted = select(func.count(), func.max(QrScanLog.scanned_at))
            publics = (
                select(func.count()).select_from(QrScanLog).where(QrScanLog.channel == "public")
            )
            if batch is not None:
                join = QrToken.id == QrScanLog.token_id
                wanted = list(batch) or [""]
                counted = counted.select_from(QrScanLog).join(QrToken, join)
                counted = counted.where(QrToken.heap_id.in_(wanted))
                publics = publics.join(QrToken, join).where(QrToken.heap_id.in_(wanted))
            if since:
                counted = counted.where(QrScanLog.scanned_at >= since)
                publics = publics.where(QrScanLog.scanned_at >= since)
            if until:
                counted = counted.where(QrScanLog.scanned_at <= until)
                publics = publics.where(QrScanLog.scanned_at <= until)
            count, batch_last = self.session.execute(counted).one()
            total += int(count or 0)
            public += int(self.session.execute(publics).scalar_one())
            if batch_last is not None and (last is None or batch_last > last):
                last = batch_last
        return total, public, last
