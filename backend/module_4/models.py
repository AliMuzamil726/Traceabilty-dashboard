"""ORM tables owned by Module 4 (Harvest Radar).

Radar owns only pickup requests. Everything it shows about fields and crops is read
from Modules 2 and 3 through their public APIs and computed on the fly.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, IdMixin, UTCDateTime, utcnow

STATUS_REQUESTED = "requested"
STATUS_SCHEDULED = "scheduled"
STATUS_FULFILLED = "fulfilled"
STATUS_CANCELLED = "cancelled"
STATUSES = (STATUS_REQUESTED, STATUS_SCHEDULED, STATUS_FULFILLED, STATUS_CANCELLED)
OPEN_STATUSES = (STATUS_REQUESTED, STATUS_SCHEDULED)

_OPEN = "status IN ('requested', 'scheduled')"


class PickupRequest(IdMixin, Base):
    """A request to collect the crop of one field for one season.

    At most one open request (requested or scheduled) per field and season: checked by
    the service inside its transaction and backed by a partial unique index.
    """

    __tablename__ = "pickup_requests"
    __table_args__ = (
        Index(
            "uq_pickup_open_per_field_season",
            "field_id",
            "season_year",
            unique=True,
            sqlite_where=text(_OPEN),
            postgresql_where=text(_OPEN),
        ),
    )

    request_no: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    field_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_code: Mapped[str] = mapped_column(String(32), nullable=False)
    farmer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(16), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_REQUESTED)
    estimated_quantity_kg: Mapped[float | None] = mapped_column(Float)
    quantity_is_estimate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preferred_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(36))
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    cancelled_by: Mapped[str | None] = mapped_column(String(36))
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    delivery_id: Mapped[str | None] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES
