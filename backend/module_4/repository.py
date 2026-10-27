"""Data access for Module 4 (Harvest Radar). The only layer that builds SQL for its tables."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from core.pagination import PageParams, PageResult, paginate
from module_4.models import OPEN_STATUSES, PickupRequest
from shared.repositories.base import BaseRepository


class PickupRequestRepository(BaseRepository[PickupRequest]):
    model = PickupRequest

    def open_for(self, field_id: str, season_year: int) -> PickupRequest | None:
        stmt = select(PickupRequest).where(
            PickupRequest.field_id == field_id,
            PickupRequest.season_year == season_year,
            PickupRequest.status.in_(OPEN_STATUSES),
        )
        return self.session.execute(stmt).scalars().first()

    def open_for_field(self, field_id: str) -> list[PickupRequest]:
        stmt = select(PickupRequest).where(
            PickupRequest.field_id == field_id, PickupRequest.status.in_(OPEN_STATUSES)
        )
        return list(self.session.execute(stmt).scalars())

    def latest_by_field(
        self, season_year: int, crop: str | None = None
    ) -> dict[str, PickupRequest]:
        """The most recent request per field for a season, cancelled ones included."""
        stmt = select(PickupRequest).where(PickupRequest.season_year == season_year)
        if crop:
            stmt = stmt.where(PickupRequest.crop == crop)
        stmt = stmt.order_by(PickupRequest.requested_at)
        out: dict[str, PickupRequest] = {}
        for row in self.session.execute(stmt).scalars():
            current = out.get(row.field_id)
            # An open request always wins over an older or cancelled one.
            if current is None or row.is_open or not current.is_open:
                out[row.field_id] = row
        return out

    def search(
        self,
        params: PageParams,
        *,
        status: str | None = None,
        crop: str | None = None,
        season_year: int | None = None,
        farmer_ids: Sequence[str] | None = None,
        open_only: bool = False,
    ) -> PageResult[PickupRequest]:
        stmt = select(PickupRequest)
        if status:
            stmt = stmt.where(PickupRequest.status == status)
        if open_only:
            stmt = stmt.where(PickupRequest.status.in_(OPEN_STATUSES))
        if crop:
            stmt = stmt.where(PickupRequest.crop == crop)
        if season_year:
            stmt = stmt.where(PickupRequest.season_year == season_year)
        if farmer_ids is not None:
            stmt = stmt.where(PickupRequest.farmer_id.in_(list(farmer_ids) or [""]))
        stmt = stmt.order_by(PickupRequest.requested_at.desc(), PickupRequest.request_no.desc())
        return paginate(self.session, stmt, params)

    def list_open(
        self, *, crop: str | None = None, season_year: int | None = None
    ) -> list[PickupRequest]:
        stmt = select(PickupRequest).where(PickupRequest.status.in_(OPEN_STATUSES))
        if crop:
            stmt = stmt.where(PickupRequest.crop == crop)
        if season_year:
            stmt = stmt.where(PickupRequest.season_year == season_year)
        return list(self.session.execute(stmt.order_by(PickupRequest.requested_at)).scalars())
