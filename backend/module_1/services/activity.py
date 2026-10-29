"""The recent activity feed: the shared audit log, read across every module.

The audit log is shared data, so it is read through
:class:`shared.repositories.audit.AuditLogRepository` rather than through any module's
public API. Each entry is turned into one line of plain English and a link to the
module that owns the record.

A field or a fieldbook entry carries no farmer in the log, and looking one up per row
would mean a query per line, so those entries link to the module's own screen rather
than to a record (D-104). Entries that do carry a usable id link straight to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.audit import ACTION_CREATE, ACTION_DELETE, ACTION_STATE_CHANGE, ACTION_UPDATE
from module_1 import config
from module_1.services import links
from module_1.services.filters import DashboardFilters
from shared.models.audit_log import AuditLog
from shared.repositories.audit import AuditLogRepository
from shared.repositories.officers import OfficerRepository

#: Which module owns each audited entity, and how to name it in a sentence.
ENTITIES: dict[str, tuple[int, str]] = {
    "farmer": (2, "Farmer"),
    "farmer_season_profile": (2, "Season details"),
    "field": (2, "Field"),
    "fieldbook": (3, "Fieldbook"),
    "fieldbook_entry": (3, "Fieldbook entry"),
    "fieldbook_photo": (3, "Fieldbook photo"),
    "pickup_request": (4, "Pickup request"),
    "delivery": (5, "Delivery"),
    "heap": (6, "Heap or batch"),
    "bale": (6, "Bale"),
    "qr_token": (7, "QR code"),
    "qr_labels": (7, "QR labels"),
    "gate_entry": (9, "Gate entry"),
}

MODULE_NAMES: dict[int, str] = {
    2: "Register Farmer",
    3: "Fieldbook",
    4: "Harvest Radar",
    5: "Deliveries",
    6: "Heap",
    7: "QR Tracing",
    9: "Gate Reception",
}

ACTIONS: dict[str, str] = {
    ACTION_CREATE: "added",
    ACTION_UPDATE: "changed",
    ACTION_DELETE: "removed",
    ACTION_STATE_CHANGE: "moved on",
}


@dataclass(frozen=True)
class ActivityItem:
    id: str
    at: datetime
    module: int
    module_name: str
    entity: str
    entity_id: str
    action: str
    summary: str
    officer_id: str | None
    officer_name: str | None
    link: links.Link

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at,
            "module": self.module,
            "module_name": self.module_name,
            "entity": self.entity,
            "entity_id": self.entity_id,
            "action": self.action,
            "summary": self.summary,
            "officer_id": self.officer_id,
            "officer_name": self.officer_name,
            "link": self.link.as_dict(),
        }


def _summary(entry: AuditLog, label: str) -> str:
    """One line: what happened, and the new state when the log records one."""
    moved = entry.diff.get("status") if isinstance(entry.diff, dict) else None
    if entry.action == ACTION_STATE_CHANGE and isinstance(moved, dict) and moved.get("to"):
        return f"{label} moved to {str(moved['to']).replace('_', ' ')}"
    return f"{label} {ACTIONS.get(entry.action, entry.action)}"


def _link(entry: AuditLog, module: int, f: DashboardFilters) -> links.Link:
    if entry.entity == "farmer":
        return links.farmer(entry.entity_id)
    if entry.entity == "fieldbook":
        return links.fieldbook(entry.entity_id)
    if entry.entity == "delivery":
        return links.delivery(entry.entity_id, f)
    if entry.entity == "gate_entry":
        return links.gate(f)
    return {
        2: links.register(f),
        3: links.fieldbook_list(),
        4: links.radar(f),
        5: links.deliveries(f),
        6: links.heaps(f),
        7: links.qr(f),
    }[module]


def build_activity(
    session: Session,
    f: DashboardFilters,
    *,
    module: int | None = None,
    limit: int = config.ACTIVITY_LIMIT,
) -> dict[str, Any]:
    """The newest audited changes, optionally from one module only."""
    wanted = [e for e, (number, _) in ENTITIES.items() if module is None or number == module]
    entries = AuditLogRepository(session).recent(
        entities=wanted, limit=min(max(1, limit), config.ACTIVITY_MAX_LIMIT)
    )
    names = {o.id: o.full_name for o in OfficerRepository(session).list_all()}
    items: list[ActivityItem] = []
    for entry in entries:
        number, label = ENTITIES[entry.entity]
        items.append(
            ActivityItem(
                id=entry.id,
                at=entry.created_at,
                module=number,
                module_name=MODULE_NAMES[number],
                entity=entry.entity,
                entity_id=entry.entity_id,
                action=entry.action,
                summary=_summary(entry, label),
                officer_id=entry.officer_id,
                officer_name=names.get(entry.officer_id or ""),
                link=_link(entry, number, f),
            )
        )
    return {
        "module": module,
        "items": [i.as_dict() for i in items],
        "modules": [{"number": n, "name": name} for n, name in sorted(MODULE_NAMES.items())],
        "generated_at": datetime.now(UTC),
    }


__all__ = ["ACTIONS", "ENTITIES", "MODULE_NAMES", "ActivityItem", "build_activity"]
