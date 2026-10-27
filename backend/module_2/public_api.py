"""Public API of Module 2 (Register Farmer).

The ONLY file other modules may import from this module. Every function takes a
``Session`` plus plain arguments and returns frozen dataclasses, never ORM rows, so a
caller cannot accidentally write to this module's tables or trigger lazy loads after
the session closes.

**Sensitive data**: full ID numbers and phone numbers are withheld unless the caller
passes ``include_sensitive=True`` *and* an ``officer_id`` that is allowed to see them
(the officer who registered the farmer, or an administrator). Anything else gets the
masked form, so a careless caller leaks nothing.

Signatures are documented in ``docs/CONTRACTS.md``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import audit
from module_2.models import Farmer, FarmerSeasonProfile, Field
from module_2.repository import FarmerRepository, FieldRepository, SeasonProfileRepository
from module_2.services.validators import mask_id_number, mask_phone
from shared.models.officer import SEES_ALL_ROLES
from shared.repositories.officers import OfficerRepository


@dataclass(frozen=True)
class FarmerDTO:
    """A farmer as other modules see them."""

    id: str
    sawie_id: int
    name: str
    crop: str
    country: str
    field_office_id: str
    registered_by: str | None
    #: Masked unless the caller was allowed to see the real value.
    id_number: str
    phone: str | None
    sensitive_included: bool
    #: Hemp only. Not sensitive: it is the grower's public licence reference, which
    #: the Fieldbook shows read-only on its first hemp step.
    home_office_licence_no: str | None = None


@dataclass(frozen=True)
class FieldDTO:
    """A mapped field. ``field_id`` is the business ID (``1001-01``); ``id`` is the key."""

    id: str
    field_id: str
    farmer_id: str
    area_m2: float
    area_acre: float
    area_ha: float
    vertex_count: int
    pin_lat: float
    pin_lng: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class SeasonProfileDTO:
    farmer_id: str
    season_year: int
    variety: str
    tenure: str
    previous_crop: str | None
    updated_at: datetime


@dataclass(frozen=True)
class RegistrationTotalsDTO:
    """Farmer and field counts for the Dashboard. Added for Module 1 (D-096).

    ``farmers_by_crop`` and ``fields_by_crop`` always carry both crops, zero included,
    so a caller can show the split without checking for missing keys. Areas are the
    sum of the fields' stored areas: acres for cotton, hectares for hemp, and both are
    given so the caller picks the unit its crop uses.
    """

    farmers: int
    farmers_by_crop: dict[str, int]
    farmers_without_field: int
    fields: int
    fields_by_crop: dict[str, int]
    area_acre: float
    area_ha: float
    area_acre_by_crop: dict[str, float]
    area_ha_by_crop: dict[str, float]


@dataclass(frozen=True)
class RegionAreaDTO:
    """Mapped area grouped by district (cotton) or county (hemp). Added for Module 1."""

    region: str
    fields: int
    area_acre: float
    area_ha: float


@dataclass(frozen=True)
class FarmerRefDTO:
    """Just enough to name a farmer in a list or an alert. Carries nothing sensitive."""

    id: str
    sawie_id: int
    name: str
    crop: str
    registered_by: str | None
    registered_at: datetime | None


@dataclass(frozen=True)
class OfficerRegistrationsDTO:
    """One officer's registration work. Added for Module 1's officer overview."""

    officer_id: str
    farmers: int
    fields: int
    area_acre: float
    area_ha: float


@dataclass(frozen=True)
class FieldSourceDTO:
    """One active field joined with the farmer details a listing needs, for bulk readers.

    Carries no ID number or phone, so it needs no sensitive-data gate.
    """

    id: str
    field_id: str
    farmer_id: str
    sawie_id: int
    farmer_name: str
    father_name: str | None
    farm_name: str | None
    crop: str
    country: str
    province: str | None
    district: str | None
    tehsil: str | None
    village: str | None
    county: str | None
    region: str | None
    field_office_id: str
    registered_by: str | None
    area_acre: float
    area_ha: float
    pin_lat: float
    pin_lng: float
    bbox: tuple[float, float, float, float]
    geometry: dict[str, Any] | None = None
    #: When the farmer was registered and the field mapped (for traceability timelines).
    farmer_registered_at: datetime | None = None
    field_mapped_at: datetime | None = None


# ------------------------------------------------------------------------ mapping


def _may_see_sensitive(session: Session, farmer: Farmer, officer_id: str | None) -> bool:
    if not officer_id:
        return False
    if farmer.registered_by == officer_id:
        return True
    officer = OfficerRepository(session).get(officer_id)
    return officer is not None and officer.role in SEES_ALL_ROLES


def _farmer_dto(
    session: Session, farmer: Farmer, *, include_sensitive: bool, officer_id: str | None
) -> FarmerDTO:
    allowed = include_sensitive and _may_see_sensitive(session, farmer, officer_id)
    return FarmerDTO(
        id=farmer.id,
        sawie_id=farmer.sawie_id,
        name=farmer.name,
        crop=farmer.crop,
        country=farmer.country,
        field_office_id=farmer.field_office_id,
        registered_by=farmer.registered_by,
        id_number=(
            farmer.id_number_display if allowed else mask_id_number(farmer.id_number_display)
        ),
        phone=(farmer.phone_display if allowed else mask_phone(farmer.phone_display)),
        sensitive_included=allowed,
        home_office_licence_no=farmer.home_office_licence_no,
    )


def _field_dto(field: Field) -> FieldDTO:
    return FieldDTO(
        id=field.id,
        field_id=field.field_id,
        farmer_id=field.farmer_id,
        area_m2=field.area_m2,
        area_acre=field.area_acre,
        area_ha=field.area_ha,
        vertex_count=field.vertex_count,
        pin_lat=field.pin_lat,
        pin_lng=field.pin_lng,
        bbox=(
            field.bbox_min_lng,
            field.bbox_min_lat,
            field.bbox_max_lng,
            field.bbox_max_lat,
        ),
    )


def _profile_dto(profile: FarmerSeasonProfile) -> SeasonProfileDTO:
    return SeasonProfileDTO(
        farmer_id=profile.farmer_id,
        season_year=profile.season_year,
        variety=profile.variety,
        tenure=profile.tenure,
        previous_crop=profile.previous_crop,
        updated_at=profile.updated_at,
    )


# ------------------------------------------------------------------------ farmers


def get_farmer(
    session: Session,
    farmer_id: str,
    *,
    include_sensitive: bool = False,
    officer_id: str | None = None,
) -> FarmerDTO | None:
    farmer = FarmerRepository(session).get(farmer_id)
    if farmer is None:
        return None
    return _farmer_dto(session, farmer, include_sensitive=include_sensitive, officer_id=officer_id)


def get_farmer_by_sawie_id(
    session: Session,
    sawie_id: int,
    *,
    include_sensitive: bool = False,
    officer_id: str | None = None,
) -> FarmerDTO | None:
    farmer = FarmerRepository(session).get_by_sawie_id(int(sawie_id))
    if farmer is None:
        return None
    return _farmer_dto(session, farmer, include_sensitive=include_sensitive, officer_id=officer_id)


def get_farmers(session: Session, farmer_ids: Sequence[str]) -> dict[str, FarmerDTO]:
    """Several farmers in one query, keyed by id (masked values)."""
    rows = FarmerRepository(session).get_many(farmer_ids)
    return {f.id: _farmer_dto(session, f, include_sensitive=False, officer_id=None) for f in rows}


def search_farmers(
    session: Session,
    query: str | None = None,
    *,
    officer_id: str | None = None,
    crop: str | None = None,
    limit: int = 20,
) -> list[FarmerDTO]:
    """Search by SAWIE ID, name, ID number fragment or phone.

    ``officer_id`` scopes the result to the farmers that officer registered; pass
    ``None`` to search every farmer.
    """
    rows = FarmerRepository(session).search_simple(
        q=query, crop=crop, registered_by=officer_id, limit=limit
    )
    return [_farmer_dto(session, f, include_sensitive=False, officer_id=officer_id) for f in rows]


def list_farmers_for_officer(session: Session, officer_id: str) -> list[FarmerDTO]:
    rows = FarmerRepository(session).list_for_officer(officer_id)
    return [_farmer_dto(session, f, include_sensitive=False, officer_id=officer_id) for f in rows]


def count_farmers(session: Session, *, country: str | None = None, crop: str | None = None) -> int:
    return FarmerRepository(session).count_filtered(country=country, crop=crop)


# ------------------------------------------------------------------------- fields


def get_field(session: Session, field_id: str) -> FieldDTO | None:
    """By primary key, or by business field ID (``1001-01``) if that is what is held."""
    repo = FieldRepository(session)
    field = repo.get_active(field_id) or repo.get_by_field_id(field_id)
    return _field_dto(field) if field is not None else None


def get_fields(session: Session, field_ids: Sequence[str]) -> dict[str, FieldDTO]:
    repo = FieldRepository(session)
    out: dict[str, FieldDTO] = {}
    for field_id in field_ids:
        field = repo.get_active(field_id)
        if field is not None:
            out[field.id] = _field_dto(field)
    return out


def list_fields_for_farmer(session: Session, farmer_id: str) -> list[FieldDTO]:
    return [_field_dto(f) for f in FieldRepository(session).list_for_farmer(farmer_id)]


def list_fields(
    session: Session,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    crop: str | None = None,
    limit: int = 2000,
) -> list[FieldDTO]:
    """Active fields, optionally restricted to a bounding box and a crop."""
    rows = FieldRepository(session).map_fields(bbox, crop=crop, limit=limit)
    return [_field_dto(field) for field, _farmer in rows]


def list_field_sources(
    session: Session, *, crop: str | None = None, include_geometry: bool = False
) -> list[FieldSourceDTO]:
    """Every active field with its farmer, in one query (no call per field)."""
    rows = FieldRepository(session).map_fields(None, crop=crop, limit=1_000_000)
    return [
        FieldSourceDTO(
            id=field.id,
            field_id=field.field_id,
            farmer_id=farmer.id,
            sawie_id=farmer.sawie_id,
            farmer_name=farmer.name,
            father_name=farmer.father_name,
            farm_name=farmer.farm_name,
            crop=farmer.crop,
            country=farmer.country,
            province=farmer.province,
            district=farmer.district,
            tehsil=farmer.tehsil,
            village=farmer.village,
            county=farmer.county,
            region=farmer.region,
            field_office_id=farmer.field_office_id,
            registered_by=farmer.registered_by,
            area_acre=field.area_acre,
            area_ha=field.area_ha,
            pin_lat=field.pin_lat,
            pin_lng=field.pin_lng,
            bbox=(field.bbox_min_lng, field.bbox_min_lat, field.bbox_max_lng, field.bbox_max_lat),
            geometry=dict(field.geometry) if include_geometry else None,
            farmer_registered_at=farmer.created_at,
            field_mapped_at=field.created_at,
        )
        for field, farmer in rows
    ]


def list_fields_in_bbox(
    session: Session, bbox: tuple[float, float, float, float], *, crop: str | None = None
) -> list[FieldDTO]:
    return list_fields(session, bbox=bbox, crop=crop)


def get_field_geometry(session: Session, field_id: str) -> dict[str, Any] | None:
    """The stored GeoJSON Polygon of a field."""
    repo = FieldRepository(session)
    field = repo.get_active(field_id) or repo.get_by_field_id(field_id)
    return dict(field.geometry) if field is not None else None


def total_area_m2(
    session: Session, *, country: str | None = None, crop: str | None = None
) -> float:
    return FieldRepository(session).total_area_m2(country=country, crop=crop)


# --------------------------------------------------------------------- aggregates
# Added for Module 1 (Dashboard, D-096): counts and sums computed in SQL, so the
# dashboard never loads whole tables to add them up. Every function here is a fixed
# number of queries whatever the size of the database.


def get_registration_totals(
    session: Session, *, registered_by: str | None = None
) -> RegistrationTotalsDTO:
    """Farmer and field counts, split by crop. Three queries."""
    farmers = FarmerRepository(session)
    by_crop = farmers.count_by_crop(registered_by=registered_by)
    field_totals = FieldRepository(session).totals_by_crop(registered_by=registered_by)
    crops = ("cotton", "hemp")
    fields_by_crop = {c: field_totals.get(c, (0, 0.0, 0.0))[0] for c in crops}
    acre_by_crop = {c: field_totals.get(c, (0, 0.0, 0.0))[1] for c in crops}
    ha_by_crop = {c: field_totals.get(c, (0, 0.0, 0.0))[2] for c in crops}
    return RegistrationTotalsDTO(
        farmers=sum(by_crop.values()),
        farmers_by_crop={c: by_crop.get(c, 0) for c in crops},
        farmers_without_field=farmers.count_without_field(registered_by=registered_by),
        fields=sum(fields_by_crop.values()),
        fields_by_crop=fields_by_crop,
        area_acre=round(sum(acre_by_crop.values()), 2),
        area_ha=round(sum(ha_by_crop.values()), 2),
        area_acre_by_crop=acre_by_crop,
        area_ha_by_crop=ha_by_crop,
    )


def count_farmers_without_field(
    session: Session, *, crop: str | None = None, registered_by: str | None = None
) -> int:
    """Farmers with no active field: not usable by Fieldbook or anything downstream."""
    return FarmerRepository(session).count_without_field(crop=crop, registered_by=registered_by)


def list_farmers_without_field(
    session: Session,
    *,
    crop: str | None = None,
    registered_by: str | None = None,
    limit: int = 5,
) -> list[FarmerRefDTO]:
    """The most recently registered farmers with no field, newest first."""
    rows = FarmerRepository(session).list_without_field(
        crop=crop, registered_by=registered_by, limit=limit
    )
    return [
        FarmerRefDTO(
            id=f.id,
            sawie_id=f.sawie_id,
            name=f.name,
            crop=f.crop,
            registered_by=f.registered_by,
            registered_at=f.created_at,
        )
        for f in rows
    ]


def registration_times(
    session: Session,
    *,
    crop: str | None = None,
    registered_by: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[datetime]:
    """When each farmer in the range was registered, oldest first, for a time series."""
    return FarmerRepository(session).registration_times(
        crop=crop, registered_by=registered_by, since=since, until=until
    )


def field_mapped_times(
    session: Session,
    *,
    crop: str | None = None,
    registered_by: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[datetime]:
    """When each active field in the range was mapped, oldest first."""
    return FieldRepository(session).mapped_times(
        crop=crop, registered_by=registered_by, since=since, until=until
    )


def area_by_region(
    session: Session, *, crop: str, registered_by: str | None = None, limit: int = 8
) -> list[RegionAreaDTO]:
    """Mapped area by district (cotton) or county (hemp), largest first. One query."""
    rows = FieldRepository(session).area_by_region(crop=crop, registered_by=registered_by)
    return [
        RegionAreaDTO(region=r[0], fields=r[1], area_acre=r[2], area_ha=r[3])
        for r in rows[: max(1, limit)]
    ]


def registrations_by_officer(
    session: Session, *, crop: str | None = None
) -> dict[str, OfficerRegistrationsDTO]:
    """Farmers and fields per officer, keyed by officer id. Two queries."""
    farmers = FarmerRepository(session).count_by_officer(crop=crop)
    fields = FieldRepository(session).totals_by_officer(crop=crop)
    return {
        officer_id: OfficerRegistrationsDTO(
            officer_id=officer_id,
            farmers=farmers.get(officer_id, 0),
            fields=fields.get(officer_id, (0, 0.0, 0.0))[0],
            area_acre=fields.get(officer_id, (0, 0.0, 0.0))[1],
            area_ha=fields.get(officer_id, (0, 0.0, 0.0))[2],
        )
        for officer_id in set(farmers) | set(fields)
    }


# ----------------------------------------------------------------- season profiles


def get_season_profile(
    session: Session, farmer_id: str, season_year: int
) -> SeasonProfileDTO | None:
    profile = SeasonProfileRepository(session).get_for_season(farmer_id, int(season_year))
    return _profile_dto(profile) if profile is not None else None


#: Farmer columns a location level is stored in, for :func:`replace_location_value`.
LOCATION_COLUMNS: dict[str, str] = {
    "province": "province",
    "district": "district",
    "tehsil": "tehsil",
    "village": "village",
    "county": "county",
    "region": "region",
}


def count_farmers_at_location(session: Session, level: str, name: str) -> int:
    """How many farmers hold this place name at this level (Settings usage counts)."""
    column = LOCATION_COLUMNS.get(level)
    if column is None:
        return 0
    return int(
        session.execute(
            select(func.count()).select_from(Farmer).where(getattr(Farmer, column) == name)
        ).scalar_one()
    )


def replace_location_value(
    session: Session, level: str, old: str, new: str, officer_id: str | None
) -> int:
    """Rename a place on every farmer that holds it, in one transaction.

    Farmers store place names as text (a tehsil may be typed by hand), so renaming or
    merging an entry in the location tree has to rewrite the farmers too, or the old
    spelling would linger and split a district's figures in two. Returns how many
    farmers changed; the caller commits. Every change is audited per farmer so the
    trail stays complete (DECISIONS D-118).
    """
    column = LOCATION_COLUMNS.get(level)
    if column is None:
        raise ValueError(f"Unknown location level {level!r}")
    if not new.strip():
        raise ValueError("The new name cannot be empty")
    farmers = list(session.execute(select(Farmer).where(getattr(Farmer, column) == old)).scalars())
    for farmer in farmers:
        setattr(farmer, column, new)
        farmer.updated_by = officer_id
        audit.record(
            "farmer",
            farmer.id,
            audit.ACTION_UPDATE,
            officer_id,
            {column: {"from": old, "to": new}},
            session=session,
        )
    session.flush()
    return len(farmers)


__all__ = [
    "LOCATION_COLUMNS",
    "FarmerDTO",
    "FarmerRefDTO",
    "FieldDTO",
    "FieldSourceDTO",
    "OfficerRegistrationsDTO",
    "RegionAreaDTO",
    "RegistrationTotalsDTO",
    "SeasonProfileDTO",
    "area_by_region",
    "count_farmers",
    "count_farmers_at_location",
    "count_farmers_without_field",
    "field_mapped_times",
    "get_farmer",
    "get_farmer_by_sawie_id",
    "get_farmers",
    "get_field",
    "get_field_geometry",
    "get_fields",
    "get_registration_totals",
    "get_season_profile",
    "list_farmers_for_officer",
    "list_farmers_without_field",
    "list_field_sources",
    "list_fields",
    "list_fields_for_farmer",
    "list_fields_in_bbox",
    "registration_times",
    "registrations_by_officer",
    "replace_location_value",
    "search_farmers",
    "total_area_m2",
]
