"""Events published by Module 6 (Heap) and the handlers and guards it registers."""

from __future__ import annotations

import logging
from typing import Any

from core import events
from core.events import Event, EventBus
from core.guards import DELIVERY_CAN_CORRECT, DELIVERY_CAN_UNASSIGN, GuardRegistry, GuardResult

logger = logging.getLogger("sawie.module_6")

PUBLISHES: tuple[str, ...] = (
    events.HEAP_OPENED,
    events.HEAP_CLOSED,
    events.BALE_CREATED,
    events.BALE_VOIDED,
)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""

SUBSCRIBES: tuple[str, ...] = (events.DELIVERY_DELIVERED, events.DELIVERY_CANCELLED)

OWNER = "module_6"


def on_delivery_changed(event: Event) -> None:
    """Pending counts and heap totals are computed on every read, so there is nothing
    stored to refresh; the subscription records the change in the log for tracing."""
    logger.debug(
        "%s %s: heap pending counts will reflect it", event.name, event.payload.get("delivery_no")
    )


def _heap_of(heap_id: str | None, session: Any) -> Any:
    from module_6.repository import HeapRepository

    if not heap_id or session is None:
        return None
    return HeapRepository(session).by_business_id(heap_id)


def can_correct(
    *, delivery_id: str, heap_id: str | None = None, session: Any = None, **_: Any
) -> GuardResult:
    """A delivery in a closed heap is part of a finished record. In an open heap the
    totals are computed from the weights, so a correction is reflected at once."""
    heap = _heap_of(heap_id, session)
    if heap is not None and heap.status == "closed":
        return GuardResult.deny(
            "heap_closed",
            f"The delivery is in {heap.heap_id}, which is closed. It can no longer be corrected.",
            delivery_id=delivery_id,
            heap_id=heap.heap_id,
        )
    return GuardResult.allow()


def can_unassign(
    *, delivery_id: str, heap_id: str | None = None, session: Any = None, **_: Any
) -> GuardResult:
    from module_6.repository import BaleRepository

    heap = _heap_of(heap_id, session)
    if heap is None:
        return GuardResult.allow()
    if heap.status == "closed":
        return GuardResult.deny(
            "heap_closed", f"{heap.heap_id} is closed.", delivery_id=delivery_id
        )
    if BaleRepository(session).active_count(heap.id) > 0:
        return GuardResult.deny(
            "heap_has_bales",
            f"{heap.heap_id} already has bales, so its deliveries are fixed.",
            delivery_id=delivery_id,
        )
    return GuardResult.allow()


can_correct.__qualname__ = "module_6.can_correct"
can_unassign.__qualname__ = "module_6.can_unassign"


def register(bus: EventBus, guards: GuardRegistry) -> None:
    bus.subscribe(events.DELIVERY_DELIVERED, on_delivery_changed)
    bus.subscribe(events.DELIVERY_CANCELLED, on_delivery_changed)
    guards.register(DELIVERY_CAN_CORRECT, can_correct, owner=OWNER)
    guards.register(DELIVERY_CAN_UNASSIGN, can_unassign, owner=OWNER)
