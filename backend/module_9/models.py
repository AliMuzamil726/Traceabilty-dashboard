"""ORM tables owned by Module 9 (Gate Reception)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActorMixin, Base, IdMixin, TimestampMixin, UTCDateTime, utcnow

PENDING = "pending"      # delivery arrived, not yet checked
ACCEPTED = "accepted"    # weighbridge done, accepted into site
REJECTED = "rejected"    # rejected at gate (wrong vehicle, refused)

STATUSES = (PENDING, ACCEPTED, REJECTED)


class GateEntry(IdMixin, TimestampMixin, ActorMixin, Base):
    """One gate entry per delivered delivery. Created when truck arrives at gate."""

    __tablename__ = "gate_entries"

    delivery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deliveries.id"), unique=True, nullable=False, index=True
    )
    delivery_no: Mapped[str] = mapped_column(String(16), nullable=False)
    site_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=PENDING, index=True)

    # Arrival
    arrived_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    vehicle_no: Mapped[str] = mapped_column(String(20), nullable=False)
    driver_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Weighbridge
    gross_weight_kg: Mapped[float | None] = mapped_column(Float)
    tare_weight_kg: Mapped[float | None] = mapped_column(Float)
    net_weight_kg: Mapped[float | None] = mapped_column(Float)
    moisture_pct: Mapped[float | None] = mapped_column(Float)

    # Decision
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rejected_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
