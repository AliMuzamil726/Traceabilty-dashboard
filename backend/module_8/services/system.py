"""What this installation is: versions, database, record counts, health and dummy data.

Nothing here reveals a secret. The database is reported by dialect and, for SQLite, by
file size; a connection URL with a password in it is masked before it leaves the
process, because this screen is read over the network and a screenshot of it travels.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from core import audit, usage
from core.config import Settings
from core.database import Base
from core.deps import CurrentOfficer
from core.events import CONFIG_CHANGED, bus
from module_8.services.backups import BACKUP_DIR, MAINTENANCE, sqlite_path
from shared.models.field_office import FieldOffice
from shared.models.officer import Officer
from shared.models.site import Site

#: Tables worth counting on the screen, in the order the chain runs.
COUNTED: Final[tuple[str, ...]] = (
    "farmers",
    "fields",
    "fieldbooks",
    "fieldbook_entries",
    "pickup_requests",
    "deliveries",
    "heaps",
    "bales",
    "qr_tokens",
    "audit_log",
    "officers",
    "field_offices",
    "sites",
    "master_lists",
    "locations",
    "app_settings",
)

_CREDENTIALS = re.compile(r"//([^:/@]+):([^@]*)@")


def mask_url(url: str) -> str:
    """``postgresql://user:secret@host/db`` becomes ``postgresql://user:***@host/db``."""
    return _CREDENTIALS.sub(lambda m: f"//{m.group(1)}:***@", url or "")


class SystemService:
    """The System information screen, and the dummy-data cleanup on it."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings

    # ----------------------------------------------------------------- overview

    def information(self) -> dict[str, Any]:
        # The engine serving this request, which in a test is not the process one.
        engine = self.session.get_bind()
        path = sqlite_path(session=self.session)
        settings = self.settings
        return {
            "app": {
                "name": getattr(settings, "app_name", "SAWIE"),
                "version": getattr(settings, "app_version", "unknown"),
                "environment": getattr(settings, "app_env", "development"),
                "server_time": datetime.now(UTC),
                "time_zone": "UTC",
                "maintenance": MAINTENANCE.active,
            },
            "runtime": {
                "python": platform.python_version(),
                "node": _node_version(),
                "platform": f"{platform.system()} {platform.release()}",
            },
            "database": {
                "dialect": engine.dialect.name if engine is not None else "unknown",
                "url": mask_url(getattr(settings, "database_url", "")),
                "file": str(path) if path else None,
                "size_bytes": path.stat().st_size if path and path.exists() else None,
            },
            "counts": self.record_counts(),
            "health": self.health(),
            "seed": self.seed_status(),
        }

    def record_counts(self) -> list[dict[str, Any]]:
        out = []
        for name in COUNTED:
            table = Base.metadata.tables.get(name)
            if table is None:  # pragma: no cover - a renamed table
                continue
            try:
                total = int(
                    self.session.execute(select(func.count()).select_from(table)).scalar_one()
                )
            except Exception:  # noqa: BLE001 - a table absent in an old database is information
                total = -1
            out.append({"table": name, "rows": total})
        return out

    # ------------------------------------------------------------------- health

    def health(self) -> list[dict[str, Any]]:
        """Each check answers ok, warn or fail with one plain sentence."""
        checks: list[dict[str, Any]] = []
        reachable = self._database_answers()
        checks.append(
            {
                "key": "database",
                "label": "Database",
                "status": "ok" if reachable else "fail",
                "detail": "Answering queries." if reachable else "The database did not answer.",
            }
        )

        storage = Path(getattr(self.settings, "upload_dir", "./storage"))
        checks.append(_writable("storage", "Upload folder", storage))
        checks.append(_writable("backups", "Backup folder", BACKUP_DIR))

        from core import app_settings

        postcode_on = bool(app_settings.setting_or("validation.postcode_lookup_enabled", True))
        checks.append(
            {
                "key": "postcode",
                "label": "UK postcode lookup",
                "status": "ok" if postcode_on else "warn",
                "detail": (
                    "Enabled. When the service cannot be reached, the bundled postcode-area "
                    "table is used instead."
                    if postcode_on
                    else "Turned off in Settings; the bundled postcode-area table is used."
                ),
            }
        )
        provider = app_settings.setting_or("map.tile_provider", "esri_imagery")
        checks.append(
            {
                "key": "tiles",
                "label": "Map tiles",
                "status": "ok",
                "detail": (
                    f"Provider '{provider}'. Use Test tiles on the Map screen to check that "
                    "this browser can reach it."
                ),
            }
        )
        return checks

    def _database_answers(self) -> bool:
        from sqlalchemy import text

        try:
            self.session.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 - the check reports the failure rather than raising
            return False
        return True

    def seed_status(self) -> dict[str, Any]:
        officers = int(self.session.execute(select(func.count()).select_from(Officer)).scalar_one())
        return {
            "seed_on_start": bool(getattr(self.settings, "seed_on_start", False)),
            "officers": officers,
            "has_reference_data": officers > 0,
        }

    # -------------------------------------------------------------- dummy data

    def dummy_data(self) -> dict[str, Any]:
        """Seeded placeholder officers, offices and sites, with what still uses them."""
        officers = [
            {
                "id": row.id,
                "code": row.code,
                "name": row.full_name,
                "usage": usage.count_usage(self.session, usage.KIND_OFFICER, row.id),
            }
            for row in self.session.execute(
                select(Officer).where(Officer.is_dummy.is_(True)).order_by(Officer.code)
            ).scalars()
        ]
        offices = [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "usage": usage.count_usage(self.session, usage.KIND_OFFICE, row.id)
                + int(
                    self.session.execute(
                        select(func.count())
                        .select_from(Officer)
                        .where(Officer.field_office_id == row.id)
                    ).scalar_one()
                ),
            }
            for row in self.session.execute(
                select(FieldOffice).where(FieldOffice.is_dummy.is_(True)).order_by(FieldOffice.code)
            ).scalars()
        ]
        sites = [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "usage": usage.count_usage(self.session, usage.KIND_SITE, row.id),
            }
            for row in self.session.execute(
                select(Site).where(Site.is_dummy.is_(True)).order_by(Site.code)
            ).scalars()
        ]
        removable = (
            sum(1 for r in officers if r["usage"] == 0)
            + sum(1 for r in offices if r["usage"] == 0)
            + sum(1 for r in sites if r["usage"] == 0)
        )
        return {
            "officers": officers,
            "offices": offices,
            "sites": sites,
            "removable": removable,
        }

    def remove_unused_dummy(self, officer: CurrentOfficer) -> dict[str, Any]:
        """Delete only the dummy rows nothing refers to. Anything used is left alone."""
        current = self.dummy_data()
        removed: dict[str, list[str]] = {"officers": [], "offices": [], "sites": []}
        kept: list[dict[str, Any]] = []

        for row in current["sites"]:
            if row["usage"] == 0:
                self.session.execute(delete(Site).where(Site.id == row["id"]))
                removed["sites"].append(row["code"])
            else:
                kept.append({"kind": "site", "code": row["code"], "usage": row["usage"]})
        for row in current["officers"]:
            # Never remove the officer doing the removing, used or not.
            if row["usage"] == 0 and row["id"] != officer.id:
                self.session.execute(delete(Officer).where(Officer.id == row["id"]))
                removed["officers"].append(row["code"])
            else:
                kept.append({"kind": "officer", "code": row["code"], "usage": row["usage"]})
        for row in current["offices"]:
            # Offices go last: an officer removed just now may have freed one.
            still_used = int(
                self.session.execute(
                    select(func.count())
                    .select_from(Officer)
                    .where(Officer.field_office_id == row["id"])
                ).scalar_one()
            ) + usage.count_usage(self.session, usage.KIND_OFFICE, row["id"])
            if still_used == 0:
                self.session.execute(delete(FieldOffice).where(FieldOffice.id == row["id"]))
                removed["offices"].append(row["code"])
            else:
                kept.append({"kind": "office", "code": row["code"], "usage": still_used})

        total = sum(len(v) for v in removed.values())
        if total:
            audit.record(
                "dummy_data",
                "cleanup",
                audit.ACTION_DELETE,
                officer.id,
                {"removed": {"from": None, "to": removed}},
                session=self.session,
            )
        self.session.commit()
        if total:
            bus.publish(
                CONFIG_CHANGED,
                {"key": "dummy_data", "group": "system"},
                officer_id=officer.id,
            )
        return {"removed": removed, "removed_total": total, "kept": kept}


def _writable(key: str, label: str, folder: Path) -> dict[str, Any]:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        ok = os.access(folder, os.W_OK)
    except OSError as exc:
        return {"key": key, "label": label, "status": "fail", "detail": str(exc)}
    free = shutil.disk_usage(folder).free if ok else 0
    return {
        "key": key,
        "label": label,
        "status": "ok" if ok else "fail",
        "detail": (
            f"{folder} is writable, {free // (1024 * 1024)} MB free."
            if ok
            else f"{folder} cannot be written to."
        ),
    }


def _node_version() -> str | None:
    """Node runs the web app, not the API, so its absence here is not a problem."""
    node = shutil.which("node")
    if not node:
        return None
    try:
        out = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - unusual environment
        return None
    return out.stdout.strip() or None


__all__ = ["COUNTED", "SystemService", "mask_url"]


def python_executable() -> str:  # pragma: no cover - diagnostics only
    return sys.executable
