"""Data access for Module 2. The only layer that builds SQL for this module's tables.

Nothing here applies business rules or officer scoping: callers pass the filters they
want. The one thing worth knowing is how overlap candidates are found - a bounding box
prefilter on indexed float columns narrows the set, and the exact geometry test happens
in :mod:`module_2.services.geometry`. That keeps the expensive work proportional to the
fields near the new boundary rather than to the whole table.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select

from core.database import utcnow
from core.pagination import PageParams, PageResult, paginate
from module_2.models import Farmer, FarmerSeasonProfile, Field, UkPostcodeCache
from shared.repositories.base import BaseRepository

#: Field IDs look like ``1001-01``; a search for "1001-01" should find the farmer too.
_MAX_SUGGESTIONS = 10


class FarmerRepository(BaseRepository[Farmer]):
    model = Farmer

    def get_by_sawie_id(self, sawie_id: int) -> Farmer | None:
        return self.find_one_by(sawie_id=sawie_id)

    def get_by_id_number(self, id_number_norm: str) -> Farmer | None:
        return self.find_one_by(id_number_norm=id_number_norm)

    def get_by_licence_no(self, licence_no: str) -> Farmer | None:
        return self.find_one_by(home_office_licence_no=licence_no)

    def get_many(self, farmer_ids: Sequence[str]) -> list[Farmer]:
        if not farmer_ids:
            return []
        stmt = select(Farmer).where(Farmer.id.in_(list(farmer_ids)))
        return list(self.session.execute(stmt).scalars().all())

    def _search_stmt(
        self,
        *,
        q: str | None = None,
        crop: str | None = None,
        country: str | None = None,
        field_office_id: str | None = None,
        registered_by: str | None = None,
    ) -> Select[tuple[Farmer]]:
        stmt = select(Farmer)
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        if country:
            stmt = stmt.where(Farmer.country == country.upper())
        if field_office_id:
            stmt = stmt.where(Farmer.field_office_id == field_office_id)
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        if q:
            term = q.strip()
            digits = "".join(ch for ch in term if ch.isdigit())
            clauses = [Farmer.name.ilike(f"%{term}%")]
            if digits:
                clauses.append(Farmer.id_number_norm.like(f"%{digits}%"))
                # phone_norm is E.164 (+923001234567), so a search for the local form
                # "0300" would never match it; the display form is matched as well.
                clauses.append(Farmer.phone_norm.like(f"%{digits}%"))
                clauses.append(Farmer.phone_display.like(f"%{term}%"))
                # A local number (03001234567) is stored as +923001234567.
                clauses.append(Farmer.phone_norm.like(f"%{digits.lstrip('0')}%"))
                if digits.isdigit() and len(digits) <= 9:
                    clauses.append(Farmer.sawie_id == int(digits))
            if term:
                clauses.append(Farmer.farm_name.ilike(f"%{term}%"))
                clauses.append(Farmer.home_office_licence_no.ilike(f"%{term}%"))
            stmt = stmt.where(or_(*clauses))
        return stmt

    def search(
        self,
        params: PageParams,
        *,
        q: str | None = None,
        crop: str | None = None,
        country: str | None = None,
        field_office_id: str | None = None,
        registered_by: str | None = None,
    ) -> PageResult[Farmer]:
        stmt = self._search_stmt(
            q=q,
            crop=crop,
            country=country,
            field_office_id=field_office_id,
            registered_by=registered_by,
        ).order_by(Farmer.created_at.desc(), Farmer.sawie_id.desc())
        return paginate(self.session, stmt, params)

    def search_simple(
        self,
        *,
        q: str | None = None,
        crop: str | None = None,
        registered_by: str | None = None,
        limit: int = 20,
    ) -> list[Farmer]:
        """Unpaginated search used by the public API for other modules."""
        stmt = (
            self._search_stmt(q=q, crop=crop, registered_by=registered_by)
            .order_by(Farmer.sawie_id)
            .limit(max(1, min(limit, 200)))
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_for_officer(self, officer_id: str) -> list[Farmer]:
        stmt = select(Farmer).where(Farmer.registered_by == officer_id).order_by(Farmer.sawie_id)
        return list(self.session.execute(stmt).scalars().all())

    def village_suggestions(
        self, tehsil: str, q: str | None, limit: int = _MAX_SUGGESTIONS
    ) -> list[str]:
        """Villages already typed in this tehsil, so spellings converge over time."""
        stmt = (
            select(Farmer.village)
            .where(Farmer.tehsil == tehsil, Farmer.village.is_not(None))
            .distinct()
            .order_by(Farmer.village)
            .limit(max(1, min(limit, 50)))
        )
        if q:
            stmt = stmt.where(Farmer.village.ilike(f"{q.strip()}%"))
        return [v for v in self.session.execute(stmt).scalars().all() if v]

    def count_filtered(
        self,
        *,
        country: str | None = None,
        crop: str | None = None,
        registered_by: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Farmer)
        if country:
            stmt = stmt.where(Farmer.country == country.upper())
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        return int(self.session.execute(stmt).scalar_one())

    # ----------------------------------------------------- aggregates (Dashboard)

    def count_by_crop(self, *, registered_by: str | None = None) -> dict[str, int]:
        """Farmers per crop programme in one query."""
        stmt = select(Farmer.crop, func.count()).group_by(Farmer.crop)
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        return {row[0]: int(row[1]) for row in self.session.execute(stmt).all()}

    def count_by_officer(self, *, crop: str | None = None) -> dict[str, int]:
        """Farmers registered per officer in one query."""
        stmt = select(Farmer.registered_by, func.count()).group_by(Farmer.registered_by)
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        return {row[0]: int(row[1]) for row in self.session.execute(stmt).all() if row[0]}

    def _without_field_stmt(
        self, *, crop: str | None = None, registered_by: str | None = None
    ) -> Select[tuple[Farmer]]:
        active_field = (
            select(Field.id)
            .where(Field.farmer_id == Farmer.id, Field.deleted_at.is_(None))
            .exists()
        )
        stmt = select(Farmer).where(~active_field)
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        return stmt

    def count_without_field(
        self, *, crop: str | None = None, registered_by: str | None = None
    ) -> int:
        """Farmers who have no active field, so the later modules cannot use them yet."""
        inner = self._without_field_stmt(crop=crop, registered_by=registered_by).subquery()
        return int(self.session.execute(select(func.count()).select_from(inner)).scalar_one())

    def list_without_field(
        self, *, crop: str | None = None, registered_by: str | None = None, limit: int = 5
    ) -> list[Farmer]:
        stmt = (
            self._without_field_stmt(crop=crop, registered_by=registered_by)
            .order_by(Farmer.created_at.desc(), Farmer.sawie_id.desc())
            .limit(max(1, min(limit, 200)))
        )
        return list(self.session.execute(stmt).scalars().all())

    def registration_times(
        self,
        *,
        crop: str | None = None,
        registered_by: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[datetime]:
        """When each farmer was registered, for a time series.

        Bucketing by day, week or month happens in the caller, not in SQL: date
        truncation differs between SQLite and Postgres, and the row count is bounded
        by the requested range (DECISIONS D-097).
        """
        stmt = select(Farmer.created_at)
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        if since:
            stmt = stmt.where(Farmer.created_at >= since)
        if until:
            stmt = stmt.where(Farmer.created_at <= until)
        return list(self.session.execute(stmt.order_by(Farmer.created_at)).scalars().all())


class SeasonProfileRepository(BaseRepository[FarmerSeasonProfile]):
    model = FarmerSeasonProfile

    def get_for_season(self, farmer_id: str, season_year: int) -> FarmerSeasonProfile | None:
        return self.find_one_by(farmer_id=farmer_id, season_year=season_year)

    def list_for_farmer(self, farmer_id: str) -> list[FarmerSeasonProfile]:
        stmt = (
            select(FarmerSeasonProfile)
            .where(FarmerSeasonProfile.farmer_id == farmer_id)
            .order_by(FarmerSeasonProfile.season_year.desc())
        )
        return list(self.session.execute(stmt).scalars().all())


class FieldRepository(BaseRepository[Field]):
    model = Field

    @staticmethod
    def _active() -> Select[tuple[Field]]:
        return select(Field).where(Field.deleted_at.is_(None))

    def get_active(self, field_uuid: str) -> Field | None:
        stmt = self._active().where(Field.id == field_uuid)
        return self.session.execute(stmt).scalars().first()

    def get_by_field_id(self, field_id: str) -> Field | None:
        stmt = self._active().where(Field.field_id == field_id)
        return self.session.execute(stmt).scalars().first()

    def list_for_farmer(self, farmer_id: str) -> list[Field]:
        stmt = self._active().where(Field.farmer_id == farmer_id).order_by(Field.field_id)
        return list(self.session.execute(stmt).scalars().all())

    def count_for_farmer(self, farmer_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Field)
            .where(Field.farmer_id == farmer_id, Field.deleted_at.is_(None))
        )
        return int(self.session.execute(stmt).scalar_one())

    def counts_by_farmer(self, farmer_ids: Sequence[str]) -> dict[str, int]:
        """Field counts for a page of farmers in one query (drives the status chips)."""
        if not farmer_ids:
            return {}
        stmt = (
            select(Field.farmer_id, func.count())
            .where(Field.farmer_id.in_(list(farmer_ids)), Field.deleted_at.is_(None))
            .group_by(Field.farmer_id)
        )
        return {row[0]: int(row[1]) for row in self.session.execute(stmt).all()}

    def bbox_candidates(
        self, bbox: tuple[float, float, float, float], *, exclude_id: str | None = None
    ) -> list[tuple[Field, Farmer]]:
        """Active fields whose bounding box intersects ``bbox``.

        ``bbox`` is ``(min_lng, min_lat, max_lng, max_lat)``.

        This is the overlap prefilter. Two boxes intersect unless one is entirely to
        one side of the other, which is the condition expressed below.
        """
        min_lng, min_lat, max_lng, max_lat = bbox
        stmt = (
            select(Field, Farmer)
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(
                Field.deleted_at.is_(None),
                Field.bbox_min_lng <= max_lng,
                Field.bbox_max_lng >= min_lng,
                Field.bbox_min_lat <= max_lat,
                Field.bbox_max_lat >= min_lat,
            )
        )
        if exclude_id:
            stmt = stmt.where(Field.id != exclude_id)
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    def map_fields(
        self,
        bbox: tuple[float, float, float, float] | None,
        *,
        crop: str | None = None,
        limit: int = 2000,
    ) -> list[tuple[Field, Farmer]]:
        """Fields for the map layer, joined with their farmer for the popup."""
        stmt = (
            select(Field, Farmer)
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(Field.deleted_at.is_(None))
        )
        if bbox is not None:
            min_lng, min_lat, max_lng, max_lat = bbox
            stmt = stmt.where(
                and_(
                    Field.bbox_min_lng <= max_lng,
                    Field.bbox_max_lng >= min_lng,
                    Field.bbox_min_lat <= max_lat,
                    Field.bbox_max_lat >= min_lat,
                )
            )
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        stmt = stmt.order_by(Field.field_id).limit(limit)
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    def count_map_fields(
        self, bbox: tuple[float, float, float, float] | None, *, crop: str | None = None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Field)
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(Field.deleted_at.is_(None))
        )
        if bbox is not None:
            min_lng, min_lat, max_lng, max_lat = bbox
            stmt = stmt.where(
                Field.bbox_min_lng <= max_lng,
                Field.bbox_max_lng >= min_lng,
                Field.bbox_min_lat <= max_lat,
                Field.bbox_max_lat >= min_lat,
            )
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        return int(self.session.execute(stmt).scalar_one())

    def total_area_m2(self, *, country: str | None = None, crop: str | None = None) -> float:
        stmt = (
            select(func.coalesce(func.sum(Field.area_m2), 0.0))
            .select_from(Field)
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(Field.deleted_at.is_(None))
        )
        if country:
            stmt = stmt.where(Farmer.country == country.upper())
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        return float(self.session.execute(stmt).scalar_one())

    # ----------------------------------------------------- aggregates (Dashboard)

    def totals_by_crop(
        self, *, registered_by: str | None = None
    ) -> dict[str, tuple[int, float, float]]:
        """``{crop: (fields, area_acre, area_ha)}`` in one query."""
        stmt = (
            select(
                Farmer.crop,
                func.count(),
                func.coalesce(func.sum(Field.area_acre), 0.0),
                func.coalesce(func.sum(Field.area_ha), 0.0),
            )
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(Field.deleted_at.is_(None))
            .group_by(Farmer.crop)
        )
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        return {
            row[0]: (int(row[1]), round(float(row[2]), 2), round(float(row[3]), 2))
            for row in self.session.execute(stmt).all()
        }

    def totals_by_officer(self, *, crop: str | None = None) -> dict[str, tuple[int, float, float]]:
        """``{officer_id: (fields, area_acre, area_ha)}`` in one query."""
        stmt = (
            select(
                Farmer.registered_by,
                func.count(),
                func.coalesce(func.sum(Field.area_acre), 0.0),
                func.coalesce(func.sum(Field.area_ha), 0.0),
            )
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(Field.deleted_at.is_(None))
            .group_by(Farmer.registered_by)
        )
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        return {
            row[0]: (int(row[1]), round(float(row[2]), 2), round(float(row[3]), 2))
            for row in self.session.execute(stmt).all()
            if row[0]
        }

    def area_by_region(
        self, *, crop: str, registered_by: str | None = None
    ) -> list[tuple[str, int, float, float]]:
        """``(region, fields, area_acre, area_ha)`` by district (cotton) or county (hemp)."""
        column = Farmer.district if crop == "cotton" else Farmer.county
        stmt = (
            select(
                column,
                func.count(),
                func.coalesce(func.sum(Field.area_acre), 0.0),
                func.coalesce(func.sum(Field.area_ha), 0.0),
            )
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(Field.deleted_at.is_(None), Farmer.crop == crop, column.is_not(None))
            .group_by(column)
        )
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        rows = [
            (str(row[0]), int(row[1]), round(float(row[2]), 2), round(float(row[3]), 2))
            for row in self.session.execute(stmt).all()
        ]
        return sorted(rows, key=lambda r: (-r[2], r[0]))

    def mapped_times(
        self,
        *,
        crop: str | None = None,
        registered_by: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[datetime]:
        """When each active field was mapped (see :meth:`FarmerRepository.registration_times`)."""
        stmt = (
            select(Field.created_at)
            .join(Farmer, Farmer.id == Field.farmer_id)
            .where(Field.deleted_at.is_(None))
        )
        if crop:
            stmt = stmt.where(Farmer.crop == crop)
        if registered_by:
            stmt = stmt.where(Farmer.registered_by == registered_by)
        if since:
            stmt = stmt.where(Field.created_at >= since)
        if until:
            stmt = stmt.where(Field.created_at <= until)
        return list(self.session.execute(stmt.order_by(Field.created_at)).scalars().all())

    def soft_delete(
        self, field: Field, officer_id: str | None, when: datetime | None = None
    ) -> Field:
        field.deleted_at = when or utcnow()
        field.deleted_by = officer_id
        field.updated_by = officer_id
        self.session.flush()
        return field


class PostcodeCacheRepository(BaseRepository[UkPostcodeCache]):
    model = UkPostcodeCache

    def get_by_postcode(self, postcode_norm: str) -> UkPostcodeCache | None:
        return self.find_one_by(postcode_norm=postcode_norm)

    def upsert(
        self, postcode_norm: str, *, county: str | None, region: str | None, source: str
    ) -> UkPostcodeCache:
        existing = self.get_by_postcode(postcode_norm)
        if existing is not None:
            existing.county = county
            existing.region = region
            existing.source = source
            existing.fetched_at = utcnow()
            self.session.flush()
            return existing
        return self.add(
            UkPostcodeCache(
                postcode_norm=postcode_norm,
                county=county,
                region=region,
                source=source,
                fetched_at=utcnow(),
            )
        )


__all__ = [
    "FarmerRepository",
    "FieldRepository",
    "PostcodeCacheRepository",
    "SeasonProfileRepository",
]
