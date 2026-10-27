"""ORM tables owned by Module 7 (QR Tracing)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, IdMixin, UTCDateTime, utcnow

TYPE_BALE = "bale"
TYPE_HEAP = "heap"
ACTIVE = "active"
REVOKED = "revoked"
CHANNEL_PUBLIC = "public"
CHANNEL_INTERNAL = "internal"


class QrToken(IdMixin, Base):
    """A random, unguessable code printed on a bale or heap label.

    ``token`` is 12 characters of base32 from ``secrets``; it is never derived from a
    serial, so knowing one bale's serial says nothing about any token.
    """

    __tablename__ = "qr_tokens"

    token: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    token_type: Mapped[str] = mapped_column(String(8), nullable=False)
    bale_serial: Mapped[str | None] = mapped_column(String(48), index=True)
    #: The heap's business ID (for example BWP-G1-H01), for bale and heap tokens alike.
    heap_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default=ACTIVE)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    revoked_by: Mapped[str | None] = mapped_column(String(36))
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    label_print_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_printed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class QrScanLog(IdMixin, Base):
    """One scan. The address is stored only as a salted SHA-256, never raw."""

    __tablename__ = "qr_scan_log"

    token_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("qr_tokens.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scanned_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    channel: Mapped[str] = mapped_column(String(8), nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent_family: Mapped[str | None] = mapped_column(String(32))
