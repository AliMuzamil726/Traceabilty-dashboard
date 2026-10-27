"""In-process, synchronous publish/subscribe event bus.

* Handlers are registered at startup (each module's ``events.register_handlers``).
* ``publish`` calls every handler in registration order, inside the caller's
  transaction (the publisher passes its session on the event).
* A failing handler is logged with a full traceback. Remaining handlers still run,
  then :class:`EventHandlerError` is raised so the unit of work rolls back.
  Failures are never swallowed silently.
* :meth:`EventBus.capture` is a test hook that records published events.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.database import utcnow

logger = logging.getLogger("sawie.events")

# Planned event names. The owning module publishes; any module may subscribe.
FARMER_REGISTERED = "farmer.registered"
FARMER_UPDATED = "farmer.updated"
FIELD_CREATED = "field.created"
FIELD_UPDATED = "field.updated"
FIELD_DELETED = "field.deleted"
FIELDBOOK_STEP_SAVED = "fieldbook.step_saved"
FIELDBOOK_SUBMITTED = "fieldbook.submitted"
FIELDBOOK_READY_FOR_PICKUP = "fieldbook.ready_for_pickup"
PICKUP_REQUESTED = "pickup.requested"
PICKUP_CANCELLED = "pickup.cancelled"
DELIVERY_SCHEDULED = "delivery.scheduled"
DELIVERY_DISPATCHED = "delivery.dispatched"
DELIVERY_DELIVERED = "delivery.delivered"
DELIVERY_CANCELLED = "delivery.cancelled"
HEAP_OPENED = "heap.opened"
HEAP_CLOSED = "heap.closed"
BALE_CREATED = "bale.created"
BALE_VOIDED = "bale.voided"
QR_SCANNED = "qr.scanned"
CONFIG_CHANGED = "config.changed"
OFFICER_CREATED = "officer.created"
OFFICER_UPDATED = "officer.updated"
OFFICER_DEACTIVATED = "officer.deactivated"
LIST_CHANGED = "list.changed"
LOCATION_CHANGED = "location.changed"
BACKUP_CREATED = "backup.created"
BACKUP_RESTORED = "backup.restored"

KNOWN_EVENTS: frozenset[str] = frozenset(
    {
        FARMER_REGISTERED,
        FARMER_UPDATED,
        FIELD_CREATED,
        FIELD_UPDATED,
        FIELD_DELETED,
        FIELDBOOK_STEP_SAVED,
        FIELDBOOK_SUBMITTED,
        FIELDBOOK_READY_FOR_PICKUP,
        PICKUP_REQUESTED,
        PICKUP_CANCELLED,
        DELIVERY_SCHEDULED,
        DELIVERY_DISPATCHED,
        DELIVERY_DELIVERED,
        DELIVERY_CANCELLED,
        HEAP_OPENED,
        HEAP_CLOSED,
        BALE_CREATED,
        BALE_VOIDED,
        QR_SCANNED,
        CONFIG_CHANGED,
        OFFICER_CREATED,
        OFFICER_UPDATED,
        OFFICER_DEACTIVATED,
        LIST_CHANGED,
        LOCATION_CHANGED,
        BACKUP_CREATED,
        BACKUP_RESTORED,
    }
)


@dataclass(frozen=True)
class Event:
    """A published fact. ``payload`` holds plain JSON-compatible values only."""

    name: str
    payload: dict[str, Any]
    officer_id: str | None = None
    occurred_at: datetime = field(default_factory=utcnow)
    session: Session | None = field(default=None, compare=False, repr=False)


Handler = Callable[[Event], None]


class EventHandlerError(RuntimeError):
    """Raised after publish when one or more handlers failed."""

    def __init__(self, event_name: str, failures: list[tuple[str, BaseException]]) -> None:
        names = ", ".join(name for name, _ in failures)
        super().__init__(f"{len(failures)} handler(s) failed for '{event_name}': {names}")
        self.event_name = event_name
        self.failures = failures


class UnknownEventError(ValueError):
    """Raised when publishing or subscribing to an event not listed in KNOWN_EVENTS."""


class EventBus:
    def __init__(self, *, strict_names: bool = True) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._captures: list[list[Event]] = []
        self.strict_names = strict_names

    def _check_name(self, name: str) -> None:
        if self.strict_names and name not in KNOWN_EVENTS:
            raise UnknownEventError(
                f"Event '{name}' is not declared in core.events.KNOWN_EVENTS "
                "(add it there and document it in docs/CONTRACTS.md)."
            )

    def subscribe(self, name: str, handler: Handler) -> None:
        self._check_name(name)
        if handler not in self._handlers[name]:
            self._handlers[name].append(handler)

    def unsubscribe(self, name: str, handler: Handler) -> None:
        if handler in self._handlers.get(name, []):
            self._handlers[name].remove(handler)

    def handlers_for(self, name: str) -> list[Handler]:
        return list(self._handlers.get(name, []))

    def clear(self) -> None:
        self._handlers.clear()

    def publish(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        officer_id: str | None = None,
        session: Session | None = None,
    ) -> Event:
        self._check_name(name)
        event = Event(name=name, payload=dict(payload), officer_id=officer_id, session=session)
        for captured in self._captures:
            captured.append(event)

        failures: list[tuple[str, BaseException]] = []
        for handler in self.handlers_for(name):
            handler_name = getattr(handler, "__qualname__", repr(handler))
            try:
                handler(event)
            except Exception as exc:
                logger.exception("Event handler %s failed for %s", handler_name, name)
                failures.append((handler_name, exc))
        if failures:
            raise EventHandlerError(name, failures)
        logger.debug("Published %s to %d handler(s)", name, len(self.handlers_for(name)))
        return event

    @contextmanager
    def capture(self) -> Iterator[list[Event]]:
        """Test hook: collect every event published inside the ``with`` block."""
        captured: list[Event] = []
        self._captures.append(captured)
        try:
            yield captured
        finally:
            self._captures.remove(captured)


bus = EventBus()
"""Process-wide bus used by the application."""
