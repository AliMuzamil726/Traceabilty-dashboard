from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from shared.models.location import Location
from shared.repositories.base import BaseRepository


class LocationRepository(BaseRepository[Location]):
    model = Location

    def get_by_code(self, code: str) -> Location | None:
        return self.find_one_by(code=code)

    def children(
        self, *, country: str, level: str, parent_id: str | None = None
    ) -> Sequence[Location]:
        stmt = select(Location).where(
            Location.country == country.upper(), Location.level == level, Location.active.is_(True)
        )
        if parent_id is not None:
            stmt = stmt.where(Location.parent_id == parent_id)
        stmt = stmt.order_by(Location.sort_order, Location.name)
        return self.session.execute(stmt).scalars().all()
