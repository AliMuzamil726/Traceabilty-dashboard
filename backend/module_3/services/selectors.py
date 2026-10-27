"""The entry dialog's three pickers: officer, then that officer's farmers, then a field.

Scoping is enforced here, not only in the UI. An ordinary officer can pick only
themself, and therefore only the farmers they registered; an administrator can pick
any officer and see that officer's farmers.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from core.errors import ForbiddenError, NotFoundError
from core.pagination import PageParams
from module_2 import public_api as registry
from module_3.models import STATUS_SUBMITTED
from module_3.repository import FieldbookRepository
from module_3.schemas import (
    FarmerCardOut,
    FarmerOptionOut,
    FieldOptionOut,
    FieldSelectorOut,
    OfficerOptionOut,
)
from shared.models.officer import SEES_ALL_ROLES
from shared.repositories.officers import OfficerRepository


class SelectorService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.books = FieldbookRepository(session)
        self.officers = OfficerRepository(session)

    def officers_for(self, officer: CurrentOfficer) -> list[OfficerOptionOut]:
        """Everyone who can register farmers: officers, staff and admins.

        An ordinary field officer only sees themself. Staff and administrators
        see the full list so they can open any registrar's fieldbooks.
        """
        if officer.role not in SEES_ALL_ROLES:
            return [
                OfficerOptionOut(
                    id=officer.id,
                    code=officer.code,
                    full_name=officer.full_name,
                    role=officer.role,
                    country=officer.country,
                    field_office_name=officer.field_office_name,
                )
            ]
        # No role filter: include officer + staff + admin (anyone who registers farmers).
        page = self.officers.search(PageParams(page=1, page_size=200))
        return [
            OfficerOptionOut(
                id=o.id,
                code=o.code,
                full_name=o.full_name,
                role=o.role,
                country=o.country,
                field_office_name=o.field_office.name if o.field_office else None,
            )
            for o in page.rows
        ]

    def _check_officer(self, officer: CurrentOfficer, officer_id: str) -> None:
        if officer.role not in SEES_ALL_ROLES and officer_id != officer.id:
            raise ForbiddenError(
                "You can only open the fieldbooks of farmers you registered.",
                code="fieldbook_forbidden",
            )

    def farmers(
        self, officer: CurrentOfficer, officer_id: str, *, q: str | None, season_year: int
    ) -> list[FarmerOptionOut]:
        """Only the farmers the chosen officer registered, searchable by SAWIE ID or name."""
        self._check_officer(officer, officer_id)
        farmers = registry.list_farmers_for_officer(self.session, officer_id)
        term = (q or "").strip().lower()
        if term:
            farmers = [f for f in farmers if term in f.name.lower() or term in str(f.sawie_id)]
        out: list[FarmerOptionOut] = []
        for farmer in farmers:
            fields = registry.list_fields_for_farmer(self.session, farmer.id)
            books = self.books.active_for_fields([f.id for f in fields], season_year)
            submitted = sum(1 for b in books.values() if b.status == STATUS_SUBMITTED)
            drafts = len(books) - submitted
            if not fields:
                status = "no_field"
            elif submitted == len(fields):
                status = "submitted"
            elif books:
                status = "in_progress"
            else:
                status = "not_started"
            out.append(
                FarmerOptionOut(
                    id=farmer.id,
                    sawie_id=farmer.sawie_id,
                    name=farmer.name,
                    crop=farmer.crop,
                    field_count=len(fields),
                    drafts=drafts,
                    submitted=submitted,
                    fieldbook_status=status,
                )
            )
        return out

    def fields(self, officer: CurrentOfficer, farmer_id: str, season_year: int) -> FieldSelectorOut:
        farmer = registry.get_farmer(self.session, farmer_id)
        if farmer is None:
            raise NotFoundError("That farmer does not exist.", code="farmer_not_found")
        if officer.role not in SEES_ALL_ROLES and farmer.registered_by != officer.id:
            raise ForbiddenError(
                "You can only open the fieldbooks of farmers you registered.",
                code="fieldbook_forbidden",
            )
        fields = registry.list_fields_for_farmer(self.session, farmer_id)
        books = self.books.active_for_fields([f.id for f in fields], season_year)
        return FieldSelectorOut(
            farmer=FarmerCardOut(
                id=farmer.id,
                sawie_id=farmer.sawie_id,
                name=farmer.name,
                crop=farmer.crop,
                country=farmer.country,
                registered_by=farmer.registered_by,
                home_office_licence_no=farmer.home_office_licence_no,
            ),
            season_year=season_year,
            items=[
                FieldOptionOut(
                    id=f.id,
                    field_id=f.field_id,
                    area_acre=round(f.area_acre, 4),
                    area_ha=round(f.area_ha, 4),
                    fieldbook_id=books[f.id].id if f.id in books else None,
                    fieldbook_status=books[f.id].status if f.id in books else "none",
                )
                for f in fields
            ],
        )
