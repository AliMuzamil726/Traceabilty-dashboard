from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from shared.models.site import Site
from shared.repositories.base import BaseRepository


class SiteRepository(BaseRepository[Site]):
    model = Site

    def get_by_code(self, code: str) -> Site | None:
        return self.session.execute(select(Site).where(Site.code == code)).scalars().first()

    def list_filtered(self, *, crop: str | None = None, active_only: bool = True) -> Sequence[Site]:
        stmt = select(Site)
        if crop:
            stmt = stmt.where(Site.crop == crop)
        if active_only:
            stmt = stmt.where(Site.active.is_(True))
        return self.session.execute(stmt.order_by(Site.code)).scalars().all()

    def get_many(self, ids: Sequence[str]) -> dict[str, Site]:
        if not ids:
            return {}
        rows = self.session.execute(select(Site).where(Site.id.in_(list(ids)))).scalars()
        return {s.id: s for s in rows}
