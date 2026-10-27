"""Reading the audit log: search, paging and a safe CSV export.

The log is append-only. Nothing here writes, updates or deletes an entry, and no route
in the product offers it: an audit trail that can be edited proves nothing. Entries
arrive from :mod:`core.audit`, which every module calls inside the transaction that
makes the change.

The export goes through :mod:`core.csvsafe`, because an officer's note or a village
name could otherwise start with ``=`` and run as a formula when the file is opened
(DECISIONS D-112).
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from core import csvsafe
from shared.models.audit_log import AuditLog
from shared.models.officer import Officer

#: Entity name -> the module that owns it, so the screen can filter by module.
ENTITY_MODULE: Final[dict[str, int]] = {
    "farmer": 2,
    "field": 2,
    "farmer_season_profile": 2,
    "fieldbook": 3,
    "fieldbook_entry": 3,
    "crop_clock_config": 3,
    "pickup_request": 4,
    "delivery": 5,
    "delivery_config": 5,
    "heap": 6,
    "bale": 6,
    "heap_config": 6,
    "qr_token": 7,
    "app_setting": 8,
    "officer": 8,
    "field_office": 8,
    "site": 8,
    "master_list": 8,
    "location": 8,
    "backup": 8,
}

MAX_PAGE_SIZE: Final = 200
#: An export is a file, so it may hold more than one screen of rows, but not the lot.
MAX_EXPORT_ROWS: Final = 10_000


class AuditService:
    """Search and export, read-only by design."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ queries

    def _filtered(
        self,
        *,
        module: int | None = None,
        entity: str | None = None,
        entity_id: str | None = None,
        officer_id: str | None = None,
        action: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> Select[tuple[AuditLog]]:
        stmt = select(AuditLog)
        if module is not None:
            names = [name for name, number in ENTITY_MODULE.items() if number == module]
            # An unknown module matches nothing rather than everything.
            stmt = stmt.where(AuditLog.entity.in_(names or ["__none__"]))
        if entity:
            stmt = stmt.where(AuditLog.entity == entity)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == str(entity_id))
        if officer_id:
            stmt = stmt.where(AuditLog.officer_id == officer_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if date_from:
            stmt = stmt.where(
                AuditLog.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
            )
        if date_to:
            end = datetime.combine(date_to, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
            stmt = stmt.where(AuditLog.created_at < end)
        return stmt

    def search(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        **filters: Any,
    ) -> dict[str, Any]:
        """One page of entries, newest first, with the total behind it."""
        size = max(1, min(int(page_size), MAX_PAGE_SIZE))
        stmt = self._filtered(**filters)
        total = int(
            self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        )
        rows = list(
            self.session.execute(
                stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset((max(1, int(page)) - 1) * size)
                .limit(size)
            )
            .scalars()
            .all()
        )
        names = self._officer_names({r.officer_id for r in rows if r.officer_id})
        return {
            "items": [self._as_dict(row, names) for row in rows],
            "total": total,
            "page": max(1, int(page)),
            "page_size": size,
        }

    def _officer_names(self, ids: set[str]) -> dict[str, str]:
        if not ids:
            return {}
        rows = self.session.execute(
            select(Officer.id, Officer.full_name).where(Officer.id.in_(list(ids)))
        ).all()
        return {str(i): str(name) for i, name in rows}

    def _as_dict(self, row: AuditLog, names: dict[str, str]) -> dict[str, Any]:
        return {
            "id": row.id,
            "entity": row.entity,
            "entity_id": row.entity_id,
            "module": ENTITY_MODULE.get(row.entity),
            "action": row.action,
            "officer_id": row.officer_id,
            "officer_name": names.get(row.officer_id or "", None),
            "diff": row.diff or {},
            "request_id": row.request_id,
            "created_at": row.created_at,
        }

    # -------------------------------------------------------------- filter help

    def facets(self) -> dict[str, Any]:
        """The entities, actions and officers actually present, for the filter boxes."""
        entities = [
            str(value)
            for (value,) in self.session.execute(
                select(AuditLog.entity).distinct().order_by(AuditLog.entity)
            ).all()
        ]
        actions = [
            str(value)
            for (value,) in self.session.execute(
                select(AuditLog.action).distinct().order_by(AuditLog.action)
            ).all()
        ]
        officers = [
            {"id": str(i), "name": str(name)}
            for i, name in self.session.execute(
                select(Officer.id, Officer.full_name).order_by(Officer.full_name)
            ).all()
        ]
        modules = sorted({ENTITY_MODULE[e] for e in entities if e in ENTITY_MODULE})
        return {
            "entities": entities,
            "actions": actions,
            "officers": officers,
            "modules": modules,
        }

    # -------------------------------------------------------------------- export

    def export_csv(self, **filters: Any) -> str:
        stmt = (
            self._filtered(**filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(MAX_EXPORT_ROWS)
        )
        rows = list(self.session.execute(stmt).scalars().all())
        names = self._officer_names({r.officer_id for r in rows if r.officer_id})

        buffer = io.StringIO()
        writer = csvsafe.writer(buffer)
        writer.writerow(
            ["When (UTC)", "Module", "Entity", "Record", "Action", "Officer", "Field", "From", "To"]
        )
        for row in rows:
            when = row.created_at.strftime("%Y-%m-%d %H:%M:%S")
            module = ENTITY_MODULE.get(row.entity)
            officer = names.get(row.officer_id or "", "")
            diff = row.diff or {}
            if not isinstance(diff, dict) or not diff:
                writer.writerow(
                    [when, module or "", row.entity, row.entity_id, row.action, officer, "", "", ""]
                )
                continue
            for field_name, change in diff.items():
                before, after = _change_pair(change)
                writer.writerow(
                    [
                        when,
                        module or "",
                        row.entity,
                        row.entity_id,
                        row.action,
                        officer,
                        field_name,
                        before,
                        after,
                    ]
                )
        return buffer.getvalue()


def _change_pair(change: Any) -> tuple[str, str]:
    """``{"from": x, "to": y}`` as two cells; anything else as one value."""
    if isinstance(change, dict) and ("from" in change or "to" in change):
        return _plain(change.get("from")), _plain(change.get("to"))
    return "", _plain(change)


def _plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


__all__ = ["ENTITY_MODULE", "MAX_EXPORT_ROWS", "AuditService"]
