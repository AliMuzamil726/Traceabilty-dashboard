"""Events published by Module 9 (Gate Reception) and the handlers it registers.

``delivery.delivered``, ``delivery.cancelled`` and ``delivery.corrected`` arrive from
the Deliveries screen (Module 5). A load that reached the gate and was then received,
cancelled or corrected there is reconciled on its gate entry, so one load never has two
open entries and never keeps a superseded weight.
"""

from __future__ import annotations

from core import audit, events
from core.database import utcnow
from core.events import Event, EventBus
from core.guards import GuardRegistry
from module_9.models import ACCEPTED, PENDING, REJECTED, GateEntry
from module_9.repository import GateRepository

PUBLISHES: tuple[str, ...] = (
    events.GATE_ENTRY_CREATED,
    events.GATE_ENTRY_ACCEPTED,
    events.GATE_ENTRY_REJECTED,
)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""

SUBSCRIBES: tuple[str, ...] = (
    events.DELIVERY_DELIVERED,
    events.DELIVERY_CANCELLED,
    events.DELIVERY_CORRECTED,
)

OWNER = "module_9"


def _pending(event: Event) -> GateEntry | None:
    if event.session is None:
        return None
    entry = GateRepository(event.session).by_delivery(str(event.payload["delivery_id"]))
    if entry is None or entry.status != PENDING:
        return None
    return entry


def on_delivery_delivered(event: Event) -> None:
    """Received from the Deliveries screen while the load was standing at the gate."""
    entry = _pending(event)
    if entry is None:
        return
    entry.status = ACCEPTED
    entry.accepted_at = utcnow()
    entry.net_weight_kg = event.payload.get("weighbridge_weight_kg")
    entry.moisture_pct = event.payload.get("moisture_pct")
    entry.updated_by = event.officer_id
    note = "Received in Deliveries."
    entry.note = f"{entry.note}\n{note}" if entry.note else note
    audit.record(
        "gate_entry",
        entry.id,
        "accept",
        event.officer_id,
        {"delivery_no": entry.delivery_no, "source": "deliveries"},
        session=event.session,
    )


def on_delivery_cancelled(event: Event) -> None:
    """Cancelled elsewhere while the load was standing at the gate."""
    entry = _pending(event)
    if entry is None:
        return
    reason = f"Delivery cancelled: {event.payload.get('reason', '')}".strip()
    entry.status = REJECTED
    entry.rejected_at = utcnow()
    entry.rejection_reason = reason[:500]
    entry.updated_by = event.officer_id
    audit.record(
        "gate_entry",
        entry.id,
        "reject",
        event.officer_id,
        {"delivery_no": entry.delivery_no, "reason": reason, "source": "deliveries"},
        session=event.session,
    )


def on_delivery_corrected(event: Event) -> None:
    """An administrator corrected the weight after the gate accepted the load."""
    if event.session is None:
        return
    entry = GateRepository(event.session).by_delivery(str(event.payload["delivery_id"]))
    if entry is None or entry.status != ACCEPTED:
        return
    entry.net_weight_kg = event.payload.get("weighbridge_weight_kg")
    entry.moisture_pct = event.payload.get("moisture_pct")
    entry.updated_by = event.officer_id
    reason = str(event.payload.get("reason", "")).strip()
    note = f"Corrected in Deliveries: {reason}" if reason else "Corrected in Deliveries."
    entry.note = f"{entry.note}\n{note}" if entry.note else note
    audit.record(
        "gate_entry",
        entry.id,
        "correct",
        event.officer_id,
        {
            "delivery_no": entry.delivery_no,
            "net_weight_kg": entry.net_weight_kg,
            "moisture_pct": entry.moisture_pct,
        },
        session=event.session,
    )


def register(bus: EventBus, _guards: GuardRegistry) -> None:
    bus.subscribe(events.DELIVERY_DELIVERED, on_delivery_delivered)
    bus.subscribe(events.DELIVERY_CANCELLED, on_delivery_cancelled)
    bus.subscribe(events.DELIVERY_CORRECTED, on_delivery_corrected)
