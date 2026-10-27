"""ORM tables owned by Module 6 (Heap). A heap is called a batch for hemp."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActorMixin, Base, IdMixin, TimestampMixin, UTCDateTime, utcnow

OPEN = "open"
CLOSED = "closed"
BALE_ACTIVE = "active"
BALE_VOIDED = "voided"


class Heap(IdMixin, TimestampMixin, ActorMixin, Base):
    __tablename__ = "heaps"

    #: Business ID: site code, -H (cotton) or -BT (hemp), and a 2-digit per-site counter.
    heap_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    site_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sites.id"), nullable=False, index=True
    )
    crop: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default=OPEN, index=True)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    opened_by: Mapped[str | None] = mapped_column(String(36))
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    closed_by: Mapped[str | None] = mapped_column(String(36))
    close_reason: Mapped[str | None] = mapped_column(Text)
    outturn_ratio_pct: Mapped[float] = mapped_column(Float, nullable=False)
    bale_unit_kg: Mapped[float] = mapped_column(Float, nullable=False)
    shiv_pct: Mapped[float | None] = mapped_column(Float)
    dust_pct: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)


class Bale(IdMixin, Base):
    __tablename__ = "bales"
    __table_args__ = (UniqueConstraint("heap_pk", "seq", name="uq_bale_heap_seq"),)

    bale_serial: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    #: The heap's primary key; its business ID is ``heap_id`` on the heap row.
    heap_pk: Mapped[str] = mapped_column(
        String(36), ForeignKey("heaps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default=BALE_ACTIVE)
    void_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    voided_by: Mapped[str | None] = mapped_column(String(36))
    voided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class HeapConfig(IdMixin, TimestampMixin, ActorMixin, Base):
    """Defaults copied into each new heap. Placeholder values to confirm with the business."""

    __tablename__ = "heap_config"

    crop: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    default_outturn_ratio_pct: Mapped[float] = mapped_column(Float, nullable=False)
    default_bale_unit_kg: Mapped[float] = mapped_column(Float, nullable=False)
    default_shiv_pct: Mapped[float | None] = mapped_column(Float)
    default_dust_pct: Mapped[float | None] = mapped_column(Float)
    #: Bumped on every save; Settings compares it to refuse a stale overwrite.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
