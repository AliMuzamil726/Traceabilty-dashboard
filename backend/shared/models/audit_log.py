from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, IdMixin, UTCDateTime, utcnow


class AuditLog(IdMixin, Base):
    """Append-only record of every create, update, delete and state change."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity", "entity_id"),)

    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    officer_id: Mapped[str | None] = mapped_column(String(36), index=True)
    diff: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
