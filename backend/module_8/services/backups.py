"""Database backups: make one, list them, download, delete and restore.

Only SQLite is backed up from inside the product. The file is copied with SQLite's
online backup API, which takes a consistent snapshot while the app keeps serving, so
nothing has to be stopped to take one. On any other database (PostgreSQL, Supabase)
the section reports that backups are managed by the host and gives the commands,
because copying a server database from inside a web request is not something this
product should attempt.

A restore is the one operation here that destroys data, so it is wrapped:

1. a **safety backup** of the current database is taken first, every time;
2. **maintenance mode** goes on, and every write in the product answers 503 while it
   lasts, so nothing is half-written into a file that is about to be replaced;
3. the file is checked (``PRAGMA integrity_check`` plus a table count) *before* it is
   put in place, so a truncated upload cannot replace a working database;
4. the file is swapped in, the pool is disposed, and the counts are compared;
5. maintenance mode is cleared in a ``finally``, so a failure cannot leave the product
   read-only.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import audit
from core.database import Database, get_process_database
from core.deps import CurrentOfficer
from core.errors import AppError, NotFoundError, ValidationAppError
from core.events import BACKUP_CREATED, BACKUP_RESTORED, bus
from module_8.models import BACKUP_MANUAL, BACKUP_SAFETY, BackupRecord
from module_8.repository import BackupRepository

logger = logging.getLogger("sawie.backup")

#: Where backup files live. Created on first use.
BACKUP_DIR: Final = Path(__file__).resolve().parents[2] / "backups"

#: A restore is confirmed by typing this exactly.
CONFIRM_PHRASE: Final = "RESTORE"

#: Tables whose row counts are compared before and after a restore.
CHECK_TABLES: Final[tuple[str, ...]] = (
    "farmers",
    "fields",
    "fieldbooks",
    "deliveries",
    "heaps",
    "bales",
    "officers",
)

AUDIT_ENTITY = "backup"


class MaintenanceError(AppError):
    """A write arrived while the database was being replaced."""

    status_code = 503
    code = "maintenance"


class _Maintenance:
    """A process-wide flag the request middleware reads before any write."""

    def __init__(self) -> None:
        self._on = False
        self._reason = ""
        self._lock = threading.Lock()

    def start(self, reason: str) -> None:
        with self._lock:
            self._on = True
            self._reason = reason

    def stop(self) -> None:
        with self._lock:
            self._on = False
            self._reason = ""

    @property
    def active(self) -> bool:
        with self._lock:
            return self._on

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason


MAINTENANCE = _Maintenance()


def is_maintenance_mode() -> bool:
    return MAINTENANCE.active


def maintenance_reason() -> str:
    return MAINTENANCE.reason


def _database() -> Database:
    database = get_process_database()
    if database is None:  # pragma: no cover - the app always sets one
        raise ValidationAppError("No database is attached to this process.", code="no_database")
    return database


def engine_for(session: Session | None) -> Any:
    """The engine actually serving this request, which in a test is not the process one."""
    if session is not None:
        bind = session.get_bind()
        if bind is not None:
            return bind
    return _database().engine


def sqlite_path(database: Database | None = None, *, session: Session | None = None) -> Path | None:
    """The file behind the engine, or ``None`` when this is not a file-backed SQLite."""
    engine = database.engine if database is not None else engine_for(session)
    if engine.dialect.name != "sqlite":
        return None
    raw = engine.url.database
    if not raw or raw == ":memory:":
        return None
    return Path(raw).resolve()


class BackupService:
    """Everything the Backup and restore screen does."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = BackupRepository(session)

    # --------------------------------------------------------------- capability

    @property
    def engine(self) -> Any:
        return engine_for(self.session)

    def status(self) -> dict[str, Any]:
        """Whether backups can be taken here, and why not when they cannot."""
        dialect = self.engine.dialect.name
        path = self.path
        if path is None:
            return {
                "supported": False,
                "dialect": dialect,
                "reason": (
                    f"This installation uses {dialect}, where backups are taken by "
                    "the database host rather than by SAWIE."
                ),
                "instructions": (
                    "Use the host's own tooling, for example "
                    "'pg_dump --format=custom --file=sawie.dump' for a PostgreSQL database, "
                    "or the automatic daily backups in the Supabase dashboard."
                ),
                "directory": None,
                "maintenance": MAINTENANCE.active,
            }
        return {
            "supported": True,
            "dialect": dialect,
            "reason": None,
            "instructions": None,
            "directory": str(BACKUP_DIR),
            "database_bytes": path.stat().st_size if path.exists() else 0,
            "maintenance": MAINTENANCE.active,
        }

    @property
    def path(self) -> Path | None:
        return sqlite_path(session=self.session)

    def _require_sqlite(self) -> Path:
        path = self.path
        if path is None:
            raise ValidationAppError(self.status()["reason"], code="backup_not_supported")
        return path

    # ------------------------------------------------------------------ listing

    def list_backups(self) -> list[dict[str, Any]]:
        """The index, with files that have gone missing marked rather than hidden."""
        out = []
        for record in self.repo.list_newest_first():
            file_path = BACKUP_DIR / record.filename
            out.append(
                {
                    "id": record.id,
                    "filename": record.filename,
                    "size_bytes": record.size_bytes,
                    "created_by": record.created_by,
                    "created_at": record.created_at,
                    "note": record.note,
                    "kind": record.kind,
                    "present": file_path.exists(),
                }
            )
        return out

    def _record(self, backup_id: str) -> BackupRecord:
        record = self.repo.get(backup_id)
        if record is None:
            raise NotFoundError("That backup does not exist.", code="backup_not_found")
        return record

    def file_for(self, backup_id: str) -> tuple[BackupRecord, Path]:
        record = self._record(backup_id)
        path = (BACKUP_DIR / record.filename).resolve()
        # The filename comes from our own index, but a path check costs nothing.
        if BACKUP_DIR.resolve() not in path.parents or not path.exists():
            raise NotFoundError("The backup file is no longer on disk.", code="backup_file_missing")
        return record, path

    # ------------------------------------------------------------------ writing

    def create(
        self, officer: CurrentOfficer, note: str | None = None, kind: str = BACKUP_MANUAL
    ) -> dict[str, Any]:
        source = self._require_sqlite()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        suffix = "-safety" if kind == BACKUP_SAFETY else ""
        filename = f"sawie-{stamp}{suffix}.db"
        target = BACKUP_DIR / filename
        counter = 1
        while target.exists():  # pragma: no cover - two backups in the same second
            filename = f"sawie-{stamp}{suffix}-{counter}.db"
            target = BACKUP_DIR / filename
            counter += 1

        _online_backup(source, target)
        size = target.stat().st_size
        record = self.repo.add_record(
            filename=filename,
            size_bytes=size,
            officer_id=officer.id,
            note=(note or "").strip()[:500] or None,
            kind=kind,
        )
        audit.record(
            AUDIT_ENTITY,
            record.id,
            audit.ACTION_CREATE,
            officer.id,
            {"filename": {"from": None, "to": filename}, "kind": {"from": None, "to": kind}},
            session=self.session,
        )
        self.session.commit()
        bus.publish(
            BACKUP_CREATED,
            {"filename": filename, "size_bytes": size, "kind": kind},
            officer_id=officer.id,
            session=self.session,
        )
        return {
            "id": record.id,
            "filename": filename,
            "size_bytes": size,
            "created_at": record.created_at,
            "kind": kind,
            "note": record.note,
            "present": True,
            "created_by": officer.id,
        }

    def delete(self, backup_id: str, officer: CurrentOfficer) -> None:
        record = self._record(backup_id)
        path = BACKUP_DIR / record.filename
        if path.exists():
            path.unlink()
        audit.record(
            AUDIT_ENTITY,
            record.id,
            audit.ACTION_DELETE,
            officer.id,
            {"filename": {"from": record.filename, "to": None}},
            session=self.session,
        )
        self.session.delete(record)
        self.session.commit()

    # ------------------------------------------------------------------ restore

    def restore(self, backup_id: str, confirm: str, officer: CurrentOfficer) -> dict[str, Any]:
        """Replace the live database with a backup, safely or not at all."""
        if (confirm or "").strip() != CONFIRM_PHRASE:
            raise ValidationAppError(
                f"Type {CONFIRM_PHRASE} to confirm that the current data will be replaced.",
                code="confirmation_required",
            )
        live = self._require_sqlite()
        record, source = self.file_for(backup_id)

        # Check the candidate before anything is touched.
        candidate = _inspect(source)
        if not candidate["ok"]:
            raise ValidationAppError(
                f"That backup file did not pass its integrity check ({candidate['integrity']}), "
                "so it was not restored.",
                code="backup_corrupt",
            )

        before = self._table_counts()
        safety = self.create(
            officer, note=f"Safety copy before restoring {record.filename}", kind=BACKUP_SAFETY
        )

        MAINTENANCE.start(f"Restoring {record.filename}")
        try:
            self.engine.dispose()
            shutil.copy2(source, live)
            for extra in ("-wal", "-shm"):
                stale = Path(str(live) + extra)
                if stale.exists():
                    stale.unlink()
            after_check = _inspect(live)
            if not after_check["ok"]:  # pragma: no cover - the candidate was checked
                raise ValidationAppError(
                    "The restored file did not pass its integrity check.", code="restore_failed"
                )
        finally:
            MAINTENANCE.stop()

        after = self._table_counts(fresh=True)
        logger.warning(
            "Database restored from %s by %s", record.filename, officer.id or "unknown officer"
        )
        from sqlalchemy.orm import Session as OrmSession

        with OrmSession(bind=self.engine) as fresh:
            audit.record(
                AUDIT_ENTITY,
                record.id,
                audit.ACTION_STATE_CHANGE,
                officer.id,
                {"restored": {"from": None, "to": record.filename}},
                session=fresh,
            )
            fresh.commit()
        bus.publish(
            BACKUP_RESTORED,
            {"filename": record.filename, "safety_backup": safety["filename"]},
            officer_id=officer.id,
        )
        return {
            "filename": record.filename,
            "safety_backup": safety["filename"],
            "integrity": after_check["integrity"],
            "counts_before": before,
            "counts_after": after,
        }

    # ---------------------------------------------------------------- integrity

    def _table_counts(self, *, fresh: bool = False) -> dict[str, int]:
        """Rows per checked table, used to show what a restore changed."""
        if not fresh:
            return _counts(self.session)
        from sqlalchemy.orm import Session as OrmSession

        with OrmSession(bind=self.engine) as session:
            return _counts(session)


def _counts(session: Session) -> dict[str, int]:
    from core.database import Base

    out: dict[str, int] = {}
    for name in CHECK_TABLES:
        table = Base.metadata.tables.get(name)
        if table is None:  # pragma: no cover - a renamed table
            continue
        try:
            out[name] = int(session.execute(select(func.count()).select_from(table)).scalar_one())
        except Exception:  # noqa: BLE001 - a table missing from an old backup is information
            out[name] = -1
    return out


def _online_backup(source: Path, target: Path) -> None:
    """SQLite's own backup API: a consistent copy taken while the app keeps running."""
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    os.chmod(target, 0o600)


def _inspect(path: Path) -> dict[str, Any]:
    """``PRAGMA integrity_check`` plus the table count, without opening the pool."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:  # pragma: no cover - unreadable file
        return {"ok": False, "integrity": str(exc), "tables": 0}
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        tables = int(
            conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        )
    except sqlite3.Error as exc:
        return {"ok": False, "integrity": str(exc), "tables": 0}
    finally:
        conn.close()
    return {"ok": integrity == "ok" and tables > 0, "integrity": integrity, "tables": tables}


__all__ = [
    "BACKUP_DIR",
    "CHECK_TABLES",
    "CONFIRM_PHRASE",
    "MAINTENANCE",
    "BackupService",
    "MaintenanceError",
    "is_maintenance_mode",
    "maintenance_reason",
    "sqlite_path",
]
