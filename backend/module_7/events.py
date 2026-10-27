"""Events published by Module 7 (QR Tracing) and the handlers it registers."""

from __future__ import annotations

from core import events
from core.events import Event, EventBus
from core.guards import GuardRegistry

PUBLISHES: tuple[str, ...] = (events.QR_SCANNED,)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""

SUBSCRIBES: tuple[str, ...] = (
    events.BALE_CREATED,
    events.BALE_VOIDED,
    events.HEAP_OPENED,
    events.HEAP_CLOSED,
)


def on_bale_created(event: Event) -> None:
    """One code per bale, created in the same transaction as the bale. Idempotent."""
    from module_7.services.tokens import TokenService

    if event.session is None:
        return
    TokenService(event.session).ensure_bale_token(
        event.payload["bale_serial"], event.payload["heap_id"], officer_id=event.officer_id
    )


def on_bale_voided(event: Event) -> None:
    from module_7.services.tokens import TokenService

    if event.session is None:
        return
    TokenService(event.session).revoke_for_bale(
        event.payload["bale_serial"],
        f"Bale voided: {event.payload.get('reason') or ''}".strip(),
        event.officer_id,
    )


def on_heap_opened(event: Event) -> None:
    from module_7.services.tokens import TokenService

    if event.session is None:
        return
    TokenService(event.session).ensure_heap_token(
        event.payload["heap_id"], officer_id=event.officer_id
    )


def on_heap_closed(event: Event) -> None:
    """The public page shows the processing dates and checks, so drop cached pages."""
    from module_7.services import cache

    del event
    cache.invalidate()


def register(bus: EventBus, guards: GuardRegistry) -> None:
    del guards
    bus.subscribe(events.BALE_CREATED, on_bale_created)
    bus.subscribe(events.BALE_VOIDED, on_bale_voided)
    bus.subscribe(events.HEAP_OPENED, on_heap_opened)
    bus.subscribe(events.HEAP_CLOSED, on_heap_closed)
