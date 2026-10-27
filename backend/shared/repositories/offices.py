from __future__ import annotations

from sqlalchemy import select

from core.pagination import PageParams, PageResult, paginate
from shared.models.field_office import FieldOffice
from shared.repositories.base import BaseRepository


class FieldOfficeRepository(BaseRepository[FieldOffice]):
    model = FieldOffice

    def get_by_code(self, code: str) -> FieldOffice | None:
        return self.find_one_by(code=code)

    def search(
        self, params: PageParams, *, country: str | None = None, active: bool | None = True
    ) -> PageResult[FieldOffice]:
        stmt = select(FieldOffice)
        if country:
            stmt = stmt.where(FieldOffice.country == country.upper())
        if active is not None:
            stmt = stmt.where(FieldOffice.active == active)
        stmt = stmt.order_by(FieldOffice.country, FieldOffice.name)
        return paginate(self.session, stmt, params)
