"""Audit trail helper used by every module on create, update, delete and state change."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from core.logging import get_request_id
from shared.models.audit_log import AuditLog

ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_STATE_CHANGE = "state_change"


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    return value


def compute_diff(
    before: Mapping[str, Any] | None, after: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Return ``{field: {"from": old, "to": new}}`` for every changed key."""
    before = before or {}
    after = after or {}
    diff: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old != new:
            diff[key] = {"from": _jsonable(old), "to": _jsonable(new)}
    return diff


def record(
    entity: str,
    entity_id: str,
    action: str,
    officer_id: str | None,
    diff: Mapping[str, Any] | None = None,
    *,
    session: Session,
) -> AuditLog:
    """Append an audit entry in the caller's transaction."""
    entry = AuditLog(
        entity=entity,
        entity_id=str(entity_id),
        action=action,
        officer_id=officer_id,
        diff=_jsonable(dict(diff or {})),
        request_id=get_request_id(),
    )
    session.add(entry)
    session.flush()
    return entry
