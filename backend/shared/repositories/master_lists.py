from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import or_, select

from shared.models.master_list import MasterList
from shared.repositories.base import BaseRepository


class MasterListRepository(BaseRepository[MasterList]):
    model = MasterList

    def list_keys(self) -> list[str]:
        stmt = select(MasterList.list_key).where(MasterList.active.is_(True)).distinct()
        return sorted(self.session.execute(stmt).scalars().all())

    def key_exists(self, list_key: str) -> bool:
        stmt = select(MasterList.id).where(MasterList.list_key == list_key).limit(1)
        return self.session.execute(stmt).first() is not None

    def options(
        self,
        list_key: str,
        *,
        country: str | None = None,
        crop: str | None = None,
        include_inactive: bool = False,
    ) -> Sequence[MasterList]:
        """Options for one list. A scope filter also keeps rows whose scope is NULL (global)."""
        stmt = select(MasterList).where(MasterList.list_key == list_key)
        if country:
            stmt = stmt.where(
                or_(MasterList.country.is_(None), MasterList.country == country.upper())
            )
        if crop:
            stmt = stmt.where(or_(MasterList.crop.is_(None), MasterList.crop == crop.lower()))
        if not include_inactive:
            stmt = stmt.where(MasterList.active.is_(True))
        stmt = stmt.order_by(MasterList.sort_order, MasterList.label)
        return self.session.execute(stmt).scalars().all()

    def find_exact(
        self, list_key: str, value: str, country: str | None, crop: str | None
    ) -> MasterList | None:
        stmt = select(MasterList).where(
            MasterList.list_key == list_key,
            MasterList.value == value,
            MasterList.country.is_(None) if country is None else MasterList.country == country,
            MasterList.crop.is_(None) if crop is None else MasterList.crop == crop,
        )
        return self.session.execute(stmt).scalars().first()
