"""Events published by Module 4 (Harvest Radar) and the handlers and guards it registers.

Registered once at startup by ``app.lifespan`` via :func:`register`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event as sa_event

from core import events
from core.events import Event, EventBus
from core.guards import FIELD_CAN_DELETE, GuardRegistry, GuardResult

logger = logging.getLogger("sawie.module_4")

PICKUP_REQUESTED = events.PICKUP_REQUESTED
PICKUP_CANCELLED = events.PICKUP_CANCELLED

PUBLISHES: tuple[str, ...] = (PICKUP_REQUESTED, PICKUP_CANCELLED)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""

SUBSCRIBES: tuple[str, ...] = (
    events.FIELDBOOK_READY_FOR_PICKUP,
    events.FIELDBOOK_STEP_SAVED,
    events.FIELD_DELETED,
    events.FIELD_UPDATED,
)

OWNER = "module_4"
FIELD_REMOVED_REASON = "The field was removed in Register Farmer."


def _invalidate_now_and_after_commit(event: Event) -> None:
    """Drop cached views now, and again once the publisher commits.

    The second drop matters: a radar read that runs between the publish and the commit
    would otherwise cache the old data for the full 30 seconds.
    """
    from module_4.services import cache

    cache.invalidate()
    if event.session is not None:
        sa_event.listen(event.session, "after_commit", lambda _s: cache.invalidate(), once=True)


def on_data_changed(event: Event) -> None:
    """Fieldbook or field data changed: the next radar read recomputes."""
    _invalidate_now_and_after_commit(event)


def on_field_deleted(event: Event) -> None:
    """A field was removed despite the guard (an administrator override): close its requests."""
    from module_4.repository import PickupRequestRepository
    from module_4.services.pickups import PickupService

    _invalidate_now_and_after_commit(event)
    session = event.session
    if session is None:
        return
    service = PickupService(session)
    for request in PickupRequestRepository(session).open_for_field(event.payload["field_id"]):
        service.cancel_request(
            request, FIELD_REMOVED_REASON, officer_id=event.officer_id, only_requested=False
        )


def _open_request_check(*, field_id: str, session: Any = None, **_: Any) -> GuardResult:
    from module_4.repository import PickupRequestRepository

    if session is None:  # pragma: no cover - every caller passes its session
        logger.error("field.can_delete called without a session; allowing")
        return GuardResult.allow()
    open_requests = PickupRequestRepository(session).open_for_field(field_id)
    if open_requests:
        return GuardResult.deny(
            "field_has_pickup_request",
            "This field has an open pickup request. Cancel it in Harvest Radar first.",
            field_id=field_id,
            request_no=open_requests[0].request_no,
        )
    return GuardResult.allow()


_open_request_check.__qualname__ = "module_4.field_has_pickup_request"


def register(bus: EventBus, guards: GuardRegistry) -> None:
    bus.subscribe(events.FIELDBOOK_READY_FOR_PICKUP, on_data_changed)
    bus.subscribe(events.FIELDBOOK_STEP_SAVED, on_data_changed)
    bus.subscribe(events.FIELD_UPDATED, on_data_changed)
    bus.subscribe(events.FIELD_DELETED, on_field_deleted)
    guards.register(FIELD_CAN_DELETE, _open_request_check, owner=OWNER)
