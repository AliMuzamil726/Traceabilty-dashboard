"""Database queries for Module 9 (Gate Reception)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from module_9.models import ACCEPTED, REJECTED, GateEntry

#: The list filter for entries that already have an outcome (accepted or rejected).
DECIDED = "decided"


def _with_status(query: Any, status: str | None) -> Any:
    if status == DECIDED:
        return query.where(GateEntry.status.in_((ACCEPTED, REJECTED)))
    if status:
        return query.where(GateEntry.status == status)
    return query


class GateRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, entry: GateEntry) -> GateEntry:
        self._s.add(entry)
        return entry

    def get(self, entry_id: str) -> GateEntry | None:
        return self._s.get(GateEntry, entry_id)

    def get_for_update(self, entry_id: str) -> GateEntry | None:
        return self._s.scalar(select(GateEntry).where(GateEntry.id == entry_id).with_for_update())

    def by_delivery(self, delivery_id: str) -> GateEntry | None:
        return self._s.scalar(select(GateEntry).where(GateEntry.delivery_id == delivery_id))

    def list_for_site(
        self,
        site_id: str,
        *,
        status: str | None = None,
        crop: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GateEntry]:
        q = select(GateEntry).where(GateEntry.site_id == site_id)
        q = _with_status(q, status)
        if crop:
            q = q.where(GateEntry.crop == crop)
        q = q.order_by(GateEntry.arrived_at.desc()).limit(limit).offset(offset)
        return list(self._s.scalars(q))

    def count_for_site(
        self, site_id: str, *, status: str | None = None, crop: str | None = None
    ) -> int:
        q = select(func.count()).select_from(GateEntry).where(GateEntry.site_id == site_id)
        q = _with_status(q, status)
        if crop:
            q = q.where(GateEntry.crop == crop)
        return self._s.scalar(q) or 0

    def existing_delivery_ids(self, site_id: str, *, crop: str | None = None) -> set[str]:
        """Deliveries that already have a gate entry at the site, whatever its outcome."""
        q = select(GateEntry.delivery_id).where(GateEntry.site_id == site_id)
        if crop:
            q = q.where(GateEntry.crop == crop)
        return set(self._s.scalars(q))

    def accepted_since(
        self, site_id: str, since: datetime, *, crop: str | None = None
    ) -> tuple[int, float]:
        """Accepted entries after ``since`` and the net kilograms they brought in."""
        q = select(func.count(), func.coalesce(func.sum(GateEntry.net_weight_kg), 0.0)).where(
            GateEntry.site_id == site_id, GateEntry.accepted_at >= since
        )
        if crop:
            q = q.where(GateEntry.crop == crop)
        count, kg = self._s.execute(q).one()
        return int(count), float(kg or 0.0)

    def rejected_since(self, site_id: str, since: datetime, *, crop: str | None = None) -> int:
        q = select(func.count()).select_from(GateEntry).where(
            GateEntry.site_id == site_id, GateEntry.rejected_at >= since
        )
        if crop:
            q = q.where(GateEntry.crop == crop)
        return self._s.scalar(q) or 0
