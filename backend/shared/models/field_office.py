from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import ActorMixin, Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from shared.models.officer import Officer


class FieldOffice(IdMixin, TimestampMixin, ActorMixin, Base):
    """A SAWIE field office. Every officer belongs to exactly one office."""

    __tablename__ = "field_offices"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    province: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL")
    )
    is_dummy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    officers: Mapped[list[Officer]] = relationship(back_populates="field_office")
