"""Tables owned by Module 8.

``app_settings`` itself lives in ``shared.models`` because ``core.app_settings`` reads
it for every module (DECISIONS D-116); Module 8 is still its only writer. The three
tables here are read and written by Settings alone:

* :class:`SettingHistory` - what a value was, what it became, who changed it and why,
  so a change can be explained and restored;
* :class:`OfficerPreference` - one row per officer for the choices that are personal
  rather than administrative (sidebar, table density, default crop);
* :class:`BackupRecord` - the index of the files in ``backend/backups/``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow

#: ``kind`` of a backup file.
BACKUP_MANUAL = "manual"
BACKUP_SAFETY = "safety"
BACKUP_KINDS = (BACKUP_MANUAL, BACKUP_SAFETY)

DENSITY_COMFORTABLE = "comfortable"
DENSITY_COMPACT = "compact"
DENSITIES = (DENSITY_COMFORTABLE, DENSITY_COMPACT)


class SettingHistory(IdMixin, Base):
    """Append-only history of one setting, one config block or one preference change."""

    __tablename__ = "settings_history"
    __table_args__ = (Index("ix_settings_history_key_time", "key", "changed_at"),)

    key: Mapped[str] = mapped_column(String(80), nullable=False)
    old_value: Mapped[Any] = mapped_column(JSON)
    new_value: Mapped[Any] = mapped_column(JSON)
    changed_by: Mapped[str | None] = mapped_column(String(36), index=True)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))


class OfficerPreference(IdMixin, TimestampMixin, Base):
    """Personal display choices. Every officer may change their own."""

    __tablename__ = "officer_preferences"

    officer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("officers.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    sidebar_collapsed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    table_density: Mapped[str] = mapped_column(
        String(16), default=DENSITY_COMFORTABLE, nullable=False
    )
    default_crop: Mapped[str | None] = mapped_column(String(16))


class BackupRecord(IdMixin, Base):
    """One file in the backup folder. The file itself is the backup; this is its index."""

    __tablename__ = "backups"

    filename: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(16), default=BACKUP_MANUAL, nullable=False)


__all__ = [
    "BACKUP_KINDS",
    "BACKUP_MANUAL",
    "BACKUP_SAFETY",
    "DENSITIES",
    "DENSITY_COMFORTABLE",
    "DENSITY_COMPACT",
    "BackupRecord",
    "OfficerPreference",
    "SettingHistory",
]
