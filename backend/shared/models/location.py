from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, IdMixin, TimestampMixin

LEVEL_PROVINCE = "province"
LEVEL_DISTRICT = "district"
LEVEL_TEHSIL = "tehsil"
LEVELS = (LEVEL_PROVINCE, LEVEL_DISTRICT, LEVEL_TEHSIL)


class Location(IdMixin, TimestampMixin, Base):
    """Administrative hierarchy: country -> province -> district -> tehsil.

    For the United Kingdom the same three levels hold region -> county -> local
    authority district, so one table serves both crop programmes.
    """

    __tablename__ = "locations"
    __table_args__ = (Index("ix_locations_country_level_parent", "country", "level", "parent_id"),)

    country: Mapped[str] = mapped_column(String(2), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="CASCADE")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
