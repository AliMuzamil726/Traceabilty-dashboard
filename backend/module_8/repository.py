"""The only place SQL is written for Module 8's own tables.

Shared reference data (officers, offices, sites, master lists, locations) keeps using
the repositories in ``shared.repositories``; this file covers the four tables Settings
owns: the stored overrides, their history, officer preferences and the backup index.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select

from core.database import utcnow
from module_8.models import BackupRecord, OfficerPreference, SettingHistory
from shared.models.app_setting import AppSetting
from shared.repositories.base import BaseRepository


class AppSettingRepository(BaseRepository[AppSetting]):
    model = AppSetting

    def get_by_key(self, key: str) -> AppSetting | None:
        return (
            self.session.execute(select(AppSetting).where(AppSetting.key == key)).scalars().first()
        )

    def all_by_key(self, keys: Sequence[str] | None = None) -> dict[str, AppSetting]:
        stmt = select(AppSetting)
        if keys is not None:
            stmt = stmt.where(AppSetting.key.in_(keys))
        return {row.key: row for row in self.session.execute(stmt).scalars()}

    def upsert(self, key: str, value: Any, officer_id: str | None) -> AppSetting:
        """Write the override and bump its version. The caller validated the value."""
        row = self.get_by_key(key)
        if row is None:
            row = AppSetting(
                key=key, value=value, version=1, created_by=officer_id, updated_by=officer_id
            )
            self.session.add(row)
        else:
            row.value = value
            row.version += 1
            row.updated_by = officer_id
        self.session.flush()
        return row

    def remove(self, key: str) -> None:
        """Drop the override, so the value falls back to .env or the default."""
        self.session.execute(delete(AppSetting).where(AppSetting.key == key))


class SettingHistoryRepository(BaseRepository[SettingHistory]):
    model = SettingHistory

    def record(
        self,
        *,
        key: str,
        old_value: Any,
        new_value: Any,
        officer_id: str | None,
        reason: str | None = None,
    ) -> SettingHistory:
        entry = SettingHistory(
            key=key,
            old_value=old_value,
            new_value=new_value,
            changed_by=officer_id,
            changed_at=utcnow(),
            reason=reason,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_for(self, key: str | None = None, *, limit: int = 50) -> list[SettingHistory]:
        stmt = select(SettingHistory).order_by(SettingHistory.changed_at.desc()).limit(limit)
        if key:
            stmt = stmt.where(SettingHistory.key == key)
        return list(self.session.execute(stmt).scalars())

    def latest_for_keys(self, keys: Sequence[str]) -> dict[str, SettingHistory]:
        """The most recent change per key, for the 'Last changed by' line."""
        out: dict[str, SettingHistory] = {}
        if not keys:
            return out
        stmt = (
            select(SettingHistory)
            .where(SettingHistory.key.in_(keys))
            .order_by(SettingHistory.changed_at.desc())
        )
        for entry in self.session.execute(stmt).scalars():
            out.setdefault(entry.key, entry)
        return out


class OfficerPreferenceRepository(BaseRepository[OfficerPreference]):
    model = OfficerPreference

    def for_officer(self, officer_id: str) -> OfficerPreference | None:
        return (
            self.session.execute(
                select(OfficerPreference).where(OfficerPreference.officer_id == officer_id)
            )
            .scalars()
            .first()
        )

    def upsert(self, officer_id: str, **values: Any) -> OfficerPreference:
        row = self.for_officer(officer_id)
        if row is None:
            row = OfficerPreference(officer_id=officer_id)
            self.session.add(row)
        for name, value in values.items():
            if value is not None:
                setattr(row, name, value)
        self.session.flush()
        return row


class BackupRepository(BaseRepository[BackupRecord]):
    model = BackupRecord

    def list_newest_first(self) -> list[BackupRecord]:
        return list(
            self.session.execute(
                select(BackupRecord).order_by(BackupRecord.created_at.desc())
            ).scalars()
        )

    def by_filename(self, filename: str) -> BackupRecord | None:
        return (
            self.session.execute(select(BackupRecord).where(BackupRecord.filename == filename))
            .scalars()
            .first()
        )

    def add_record(
        self,
        *,
        filename: str,
        size_bytes: int,
        officer_id: str | None,
        note: str | None,
        kind: str,
        created_at: datetime | None = None,
    ) -> BackupRecord:
        record = BackupRecord(
            filename=filename,
            size_bytes=size_bytes,
            created_by=officer_id,
            note=note,
            kind=kind,
            created_at=created_at or utcnow(),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def total_bytes(self) -> int:
        return int(
            self.session.execute(
                select(func.coalesce(func.sum(BackupRecord.size_bytes), 0))
            ).scalar_one()
        )


__all__ = [
    "AppSettingRepository",
    "BackupRepository",
    "OfficerPreferenceRepository",
    "SettingHistoryRepository",
]
