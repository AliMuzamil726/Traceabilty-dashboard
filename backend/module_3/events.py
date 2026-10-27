"""Events published by Module 3 (Fieldbook), the events it listens to, and its guards.

Guards let Module 3 refuse actions Module 2 owns, without Module 2 importing it:

* ``field.can_delete`` and ``field.can_edit_geometry`` are denied once a submitted
  (locked) fieldbook exists for the field. A submitted fieldbook records what was grown
  on that exact boundary, so the boundary must not change or vanish under it.

A draft does not block anything. When Module 2 removes a field that has a draft, the
``field.deleted`` handler soft-removes the draft so it stops appearing in selectors.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import audit, events, usage
from core.database import utcnow
from core.events import Event, EventBus
from core.guards import FIELD_CAN_DELETE, FIELD_CAN_EDIT_GEOMETRY, GuardRegistry, GuardResult

logger = logging.getLogger("sawie.module_3.events")

PUBLISHES: tuple[str, ...] = (
    events.FIELDBOOK_STEP_SAVED,
    events.FIELDBOOK_SUBMITTED,
    events.FIELDBOOK_READY_FOR_PICKUP,
)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""

SUBSCRIBES: tuple[str, ...] = (events.FIELD_DELETED,)

OWNER = "module_3"


def _submitted_check(deny_code: str, message: str) -> Any:
    """A guard check that denies once a submitted fieldbook exists for the field.

    It reads through the caller's session (passed in the guard context), so it sees
    the caller's transaction and never waits on the caller's own write lock.
    """

    def check(*, field_id: str, session: Any = None, **_: Any) -> GuardResult:
        from module_3.repository import FieldbookRepository

        if session is None:  # pragma: no cover - every caller passes its session
            logger.error("Guard %s called without a session; allowing", deny_code)
            return GuardResult.allow()
        if FieldbookRepository(session).has_submitted(field_id):
            return GuardResult.deny(deny_code, message, field_id=field_id)
        return GuardResult.allow()

    check.__qualname__ = f"module_3.{deny_code}"
    return check


def on_field_deleted(event: Event) -> None:
    """Soft-remove draft fieldbooks of a field Module 2 just removed."""
    from module_3.repository import FieldbookRepository

    session = event.session
    if session is None:
        return
    field_id = event.payload["field_id"]
    for book in FieldbookRepository(session).drafts_for_field(field_id):
        book.deleted_at = utcnow()
        book.updated_by = event.officer_id
        audit.record(
            "fieldbook",
            book.id,
            audit.ACTION_DELETE,
            event.officer_id,
            {
                "deleted_at": {"from": None, "to": book.deleted_at},
                "reason": {"from": None, "to": "field removed in Register Farmer"},
            },
            session=session,
        )
        logger.warning("Draft fieldbook %s removed with its field %s", book.id, field_id)
    session.flush()


def _count_list_value(session: Session, key: str) -> int:
    """Fieldbook entries whose answers hold this value.

    Entries store answers as JSON, and the stored form is always the value *key*
    (``drip``), never the label, which is what lets Settings rename a label safely.
    The JSON is scanned in Python because the shape differs per form step and a
    portable JSON query would not survive the move to Postgres.
    """
    from module_3.models import FieldbookEntry

    _, _, value = key.partition(":")
    if not value:
        return 0
    total = 0
    rows = session.execute(select(FieldbookEntry.data)).scalars()
    for data in rows:
        if _holds(data, value):
            total += 1
    return total


def _holds(data: object, value: str) -> bool:
    if isinstance(data, str):
        return data == value
    if isinstance(data, dict):
        return any(_holds(v, value) for v in data.values())
    if isinstance(data, list):
        return any(_holds(v, value) for v in data)
    return False


def _count_officer(session: Session, officer_id: str) -> int:
    from module_3.models import Fieldbook

    return int(
        session.execute(
            select(func.count()).select_from(Fieldbook).where(Fieldbook.created_by == officer_id)
        ).scalar_one()
    )


def register(bus: EventBus, guards: GuardRegistry) -> None:
    """Subscribe handlers and register guard checks."""
    bus.subscribe(events.FIELD_DELETED, on_field_deleted)
    guards.register(
        FIELD_CAN_DELETE,
        _submitted_check(
            "field_has_fieldbook",
            "This field has a submitted fieldbook, so it cannot be removed.",
        ),
        owner=OWNER,
    )
    guards.register(
        FIELD_CAN_EDIT_GEOMETRY,
        _submitted_check(
            "field_has_fieldbook",
            "This field has a submitted fieldbook, so its boundary cannot be changed.",
        ),
        owner=OWNER,
    )
    usage.register_counter(usage.KIND_LIST_VALUE, 3, "Fieldbook entries", _count_list_value)
    usage.register_counter(usage.KIND_OFFICER, 3, "Fieldbooks", _count_officer)
