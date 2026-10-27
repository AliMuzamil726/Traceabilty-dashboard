from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from core.pagination import PageParams, PageResult, paginate
from shared.models.officer import Officer
from shared.repositories.base import BaseRepository


class OfficerRepository(BaseRepository[Officer]):
    model = Officer

    def get_with_office(self, officer_id: str) -> Officer | None:
        stmt = (
            select(Officer)
            .options(joinedload(Officer.field_office))
            .where(Officer.id == officer_id)
        )
        return self.session.execute(stmt).scalars().first()

    def get_by_code(self, code: str) -> Officer | None:
        stmt = select(Officer).options(joinedload(Officer.field_office)).where(Officer.code == code)
        return self.session.execute(stmt).scalars().first()

    def search(
        self,
        params: PageParams,
        *,
        country: str | None = None,
        field_office_id: str | None = None,
        role: str | None = None,
        q: str | None = None,
        active: bool | None = True,
    ) -> PageResult[Officer]:
        stmt = select(Officer).options(joinedload(Officer.field_office))
        if country:
            stmt = stmt.where(Officer.country == country.upper())
        if field_office_id:
            stmt = stmt.where(Officer.field_office_id == field_office_id)
        if role:
            stmt = stmt.where(Officer.role == role)
        if active is not None:
            stmt = stmt.where(Officer.active == active)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(or_(Officer.full_name.ilike(like), Officer.code.ilike(like)))
        stmt = stmt.order_by(Officer.role, Officer.country.desc(), Officer.code)
        return paginate(self.session, stmt, params)
