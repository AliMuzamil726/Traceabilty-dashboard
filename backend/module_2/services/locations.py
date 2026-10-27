"""Administrative location cascade: province to district to tehsil, then a typed village.

The rows live in the shared ``locations`` table (seeded by ``scripts/seed.py``), so
this service only reads them through the shared repository. Villages are deliberately
not seeded: there are tens of thousands and the lists go stale, so the officer types
the village and the suggestion endpoint offers what other officers already typed in
that tehsil, which makes spellings converge without freezing a list.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.errors import NotFoundError
from module_2.repository import FarmerRepository
from module_2.services.validators import sanitise_text
from shared.models.location import LEVEL_DISTRICT, LEVEL_PROVINCE, LEVEL_TEHSIL
from shared.repositories.locations import LocationRepository


@dataclass(frozen=True)
class LocationOption:
    """One administrative area, shaped like every other dropdown option."""

    value: str  # the location code, e.g. PK-PB-MUL
    label: str
    level: str
    parent_code: str | None


class LocationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.locations = LocationRepository(session)
        self.farmers = FarmerRepository(session)

    def _require(self, code: str) -> str:
        location = self.locations.get_by_code(code)
        if location is None:
            raise NotFoundError(
                f"Unknown location code '{code}'.",
                code="location_not_found",
                details={"code": code},
            )
        return location.id

    def provinces(self, country: str) -> list[LocationOption]:
        rows = self.locations.children(country=country, level=LEVEL_PROVINCE)
        return [
            LocationOption(value=r.code, label=r.name, level=r.level, parent_code=None)
            for r in rows
        ]

    def districts(self, country: str, province_code: str) -> list[LocationOption]:
        parent_id = self._require(province_code)
        rows = self.locations.children(country=country, level=LEVEL_DISTRICT, parent_id=parent_id)
        return [
            LocationOption(value=r.code, label=r.name, level=r.level, parent_code=province_code)
            for r in rows
        ]

    def tehsils(self, country: str, district_code: str) -> list[LocationOption]:
        """Tehsils of a district. May be empty: the form then offers manual entry."""
        parent_id = self._require(district_code)
        rows = self.locations.children(country=country, level=LEVEL_TEHSIL, parent_id=parent_id)
        return [
            LocationOption(value=r.code, label=r.name, level=r.level, parent_code=district_code)
            for r in rows
        ]

    def village_suggestions(self, tehsil: str, query: str | None, limit: int = 10) -> list[str]:
        name = sanitise_text(tehsil)
        if not name:
            return []
        return self.farmers.village_suggestions(name, sanitise_text(query), limit=limit)

    def resolve_name(self, code: str | None) -> str | None:
        """Display name of a location code, or ``None`` when there is no code."""
        if not code:
            return None
        location = self.locations.get_by_code(code)
        return location.name if location else None
