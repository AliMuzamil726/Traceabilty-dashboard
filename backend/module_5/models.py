"""ORM tables owned by Module 5 (Deliveries). All weights are kilograms."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActorMixin, Base, IdMixin, TimestampMixin, UTCDateTime, utcnow

SCHEDULED = "scheduled"
IN_TRANSIT = "in_transit"
DELIVERED = "delivered"
CANCELLED = "cancelled"
STATUSES = (SCHEDULED, IN_TRANSIT, DELIVERED, CANCELLED)

#: The only allowed transitions. Anything else is 409 invalid_transition.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    SCHEDULED: (IN_TRANSIT, CANCELLED),
    IN_TRANSIT: (DELIVERED, CANCELLED),
    DELIVERED: (),
    CANCELLED: (),
}

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_FLAG = "flag"


class Delivery(IdMixin, TimestampMixin, ActorMixin, Base):
    __tablename__ = "deliveries"

    delivery_no: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    pickup_request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    farmer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_code: Mapped[str] = mapped_column(String(32), nullable=False)
    crop: Mapped[str] = mapped_column(String(16), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SCHEDULED, index=True)
    site_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sites.id"), nullable=False, index=True
    )
    #: The heap's business ID (for example BWP-G1-H01), set by Module 6.
    heap_id: Mapped[str | None] = mapped_column(String(32), index=True)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    driver_name: Mapped[str] = mapped_column(String(120), nullable=False)
    driver_phone: Mapped[str] = mapped_column(String(24), nullable=False)
    vehicle_no: Mapped[str] = mapped_column(String(20), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    estimated_quantity_kg: Mapped[float | None] = mapped_column(Float)
    field_weight_kg: Mapped[float | None] = mapped_column(Float)
    weighbridge_weight_kg: Mapped[float | None] = mapped_column(Float)
    moisture_pct: Mapped[float | None] = mapped_column(Float)
    variance_kg: Mapped[float | None] = mapped_column(Float)
    variance_pct: Mapped[float | None] = mapped_column(Float)
    variance_level: Mapped[str | None] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)


class DeliveryStatusHistory(IdMixin, Base):
    __tablename__ = "delivery_status_history"

    delivery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    officer_id: Mapped[str | None] = mapped_column(String(36))
    at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class DeliveryConfig(IdMixin, TimestampMixin, ActorMixin, Base):
    """Per-crop thresholds, seeded at startup and editable later in Settings."""

    __tablename__ = "delivery_config"

    crop: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    variance_warn_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    variance_flag_pct: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    moisture_warn_pct: Mapped[float] = mapped_column(Float, nullable=False)
    #: Bumped on every save; Settings compares it to refuse a stale overwrite.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
