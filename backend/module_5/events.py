"""Events published by Module 5 (Deliveries) and the handlers and guards it registers."""

from __future__ import annotations

import logging
from typing import Any

from core import events
from core.events import Event, EventBus
from core.guards import FIELD_CAN_DELETE, FIELD_CAN_EDIT_GEOMETRY, GuardRegistry, GuardResult

logger = logging.getLogger("sawie.module_5")

PUBLISHES: tuple[str, ...] = (
    events.DELIVERY_SCHEDULED,
    events.DELIVERY_DISPATCHED,
    events.DELIVERY_DELIVERED,
    events.DELIVERY_CANCELLED,
)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""

SUBSCRIBES: tuple[str, ...] = (events.PICKUP_CANCELLED, events.FIELD_DELETED)

OWNER = "module_5"


def on_pickup_cancelled(event: Event) -> None:
    """A request was closed in Radar or by Module 5 itself: cancel any delivery still moving."""
    from module_5.repository import DeliveryRepository
    from module_5.services.deliveries import DeliveryService

    if event.session is None:
        return
    service = DeliveryService(event.session)
    for d in DeliveryRepository(event.session).open_for_request(event.payload["pickup_request_id"]):
        service.cancel_delivery(
            d,
            f"Pickup request {event.payload.get('request_no', '')} was cancelled.".replace(
                "  ", " "
            ),
            officer_id=event.officer_id,
            release_request=False,
        )


def on_field_deleted(event: Event) -> None:
    """The field was removed despite the guard (an administrator override)."""
    from module_5.repository import DeliveryRepository
    from module_5.services.deliveries import DeliveryService

    if event.session is None:
        return
    service = DeliveryService(event.session)
    for d in DeliveryRepository(event.session).active_for_field(event.payload["field_id"]):
        if d.status in ("scheduled", "in_transit"):
            service.cancel_delivery(
                d,
                "The field was removed in Register Farmer.",
                officer_id=event.officer_id,
                release_request=False,
            )


def _delivery_check(message: str) -> Any:
    def check(*, field_id: str, session: Any = None, **_: Any) -> GuardResult:
        from module_5.repository import DeliveryRepository

        if session is None:  # pragma: no cover - every caller passes its session
            logger.error("Guard called without a session; allowing")
            return GuardResult.allow()
        active = DeliveryRepository(session).active_for_field(field_id)
        if active:
            return GuardResult.deny(
                "field_has_delivery", message, field_id=field_id, delivery_no=active[0].delivery_no
            )
        return GuardResult.allow()

    check.__qualname__ = "module_5.field_has_delivery"
    return check


def register(bus: EventBus, guards: GuardRegistry) -> None:
    bus.subscribe(events.PICKUP_CANCELLED, on_pickup_cancelled)
    bus.subscribe(events.FIELD_DELETED, on_field_deleted)
    guards.register(
        FIELD_CAN_DELETE,
        _delivery_check("This field has a delivery, so it cannot be removed."),
        owner=OWNER,
    )
    guards.register(
        FIELD_CAN_EDIT_GEOMETRY,
        _delivery_check("This field has a delivery, so its boundary cannot be changed."),
        owner=OWNER,
    )
