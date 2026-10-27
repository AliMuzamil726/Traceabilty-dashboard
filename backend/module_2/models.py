"""ORM tables owned by Module 2 (Register Farmer).

Four tables, all documented in ``docs/DATA_MODEL.md``:

* ``farmers`` - permanent personal data. One row per person for life, keyed by the
  normalised ID number; the SAWIE ID never changes and is never reissued.
* ``farmer_season_profiles`` - the crop data that changes every season (variety,
  tenure, previous crop). Keeping it separate is what lets a farmer come back next
  season without a duplicate personal record.
* ``fields`` - mapped field boundaries with their derived areas (soft deleted).
* ``uk_postcode_cache`` - answers from the postcode lookup, so the same postcode is
  resolved once.

Portability: no PostGIS. Geometry is GeoJSON in a JSON column plus four bbox floats
indexed together for viewport and overlap prefiltering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from core.database import ActorMixin, Base, IdMixin, TimestampMixin, UTCDateTime

CROP_COTTON = "cotton"
CROP_HEMP = "hemp"
CROPS = (CROP_COTTON, CROP_HEMP)

COUNTRY_PK = "PK"
COUNTRY_GB = "GB"

#: Cotton is grown by Pakistani farmers, hemp by UK farmers: the crop decides the
#: country everywhere in the product, so the mapping lives in one place.
CROP_COUNTRY: dict[str, str] = {CROP_COTTON: COUNTRY_PK, CROP_HEMP: COUNTRY_GB}

#: GeoJSON is stored as JSONB on Postgres and as JSON on SQLite.
GeoJSONType = JSON().with_variant(JSONB(), "postgresql")


class Farmer(IdMixin, TimestampMixin, ActorMixin, Base):
    """A registered farmer. Personal data only; crop data lives in the season profile."""

    __tablename__ = "farmers"
    __table_args__ = (
        Index("ix_farmers_crop_office", "crop", "field_office_id"),
        Index("ix_farmers_registered_by", "registered_by"),
        Index("ix_farmers_name", "name"),
        Index("ix_farmers_tehsil_village", "tehsil", "village"),
    )

    sawie_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(16), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)

    # Identity. The normalised form is the uniqueness key; the display form keeps the
    # officer's formatting (12345-1234567-1).
    id_number_norm: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    id_number_display: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    father_name: Mapped[str | None] = mapped_column(String(60))  # cotton only
    farm_name: Mapped[str | None] = mapped_column(String(80))  # hemp only

    # Contact
    phone_norm: Mapped[str | None] = mapped_column(String(20))
    phone_display: Mapped[str | None] = mapped_column(String(24))

    # Location. Names are stored as entered (a tehsil may be typed manually), and
    # location_id points at the seeded administrative row when one was chosen.
    province: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    tehsil: Mapped[str | None] = mapped_column(String(120))
    village: Mapped[str | None] = mapped_column(String(120))  # cotton, typed manually
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL")
    )

    # Hemp (United Kingdom)
    home_office_licence_no: Mapped[str | None] = mapped_column(String(30), unique=True)
    postcode_norm: Mapped[str | None] = mapped_column(String(10))
    county: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))

    field_office_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("field_offices.id", ondelete="RESTRICT"), nullable=False
    )
    #: Officer who first registered this farmer (never changes afterwards).
    registered_by: Mapped[str | None] = mapped_column(String(36))

    season_profiles: Mapped[list[FarmerSeasonProfile]] = relationship(
        back_populates="farmer", cascade="all, delete-orphan"
    )
    fields: Mapped[list[Field]] = relationship(
        back_populates="farmer", cascade="all, delete-orphan"
    )


class FarmerSeasonProfile(IdMixin, TimestampMixin, ActorMixin, Base):
    """This season's crop data for one farmer. Upserted on every registration."""

    __tablename__ = "farmer_season_profiles"
    __table_args__ = (UniqueConstraint("farmer_id", "season_year", name="uq_farmer_season"),)

    farmer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    variety: Mapped[str] = mapped_column(String(64), nullable=False)
    tenure: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_crop: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)

    farmer: Mapped[Farmer] = relationship(back_populates="season_profiles")


class Field(IdMixin, TimestampMixin, ActorMixin, Base):
    """A mapped field boundary. Geometry is a single-ring GeoJSON Polygon in WGS84."""

    __tablename__ = "fields"
    __table_args__ = (
        Index("ix_fields_bbox", "bbox_min_lng", "bbox_min_lat", "bbox_max_lng", "bbox_max_lat"),
        Index("ix_fields_farmer_active", "farmer_id", "deleted_at"),
    )

    #: Business ID, ``{sawie_id}-{nn}`` (for example 1001-01). Never reused.
    field_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    farmer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False
    )
    geometry: Mapped[dict[str, Any]] = mapped_column(GeoJSONType, nullable=False)

    bbox_min_lat: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_min_lng: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_max_lat: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_max_lng: Mapped[float] = mapped_column(Float, nullable=False)

    #: Representative point: the centroid unless the officer placed a pin.
    pin_lat: Mapped[float] = mapped_column(Float, nullable=False)
    pin_lng: Mapped[float] = mapped_column(Float, nullable=False)

    vertex_count: Mapped[int] = mapped_column(Integer, nullable=False)
    area_m2: Mapped[float] = mapped_column(Float, nullable=False)
    area_acre: Mapped[float] = mapped_column(Float, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)

    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    deleted_by: Mapped[str | None] = mapped_column(String(36))

    farmer: Mapped[Farmer] = relationship(back_populates="fields")

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None


class UkPostcodeCache(IdMixin, Base):
    """Resolved UK postcode: county and region, and where the answer came from."""

    __tablename__ = "uk_postcode_cache"

    postcode_norm: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    county: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    #: ``postcodes_io``, ``area_table`` or ``manual``.
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


__all__ = [
    "COUNTRY_GB",
    "COUNTRY_PK",
    "CROPS",
    "CROP_COTTON",
    "CROP_COUNTRY",
    "CROP_HEMP",
    "Farmer",
    "FarmerSeasonProfile",
    "Field",
    "UkPostcodeCache",
]
