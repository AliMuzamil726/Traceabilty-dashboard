import logging

import pytest

from core.events import (
    FARMER_REGISTERED,
    FIELD_CREATED,
    KNOWN_EVENTS,
    Event,
    EventBus,
    EventHandlerError,
    UnknownEventError,
)

EXPECTED_EVENTS = {
    "farmer.registered",
    "farmer.updated",
    "field.created",
    "field.updated",
    "field.deleted",
    "fieldbook.step_saved",
    "fieldbook.submitted",
    "fieldbook.ready_for_pickup",
    "pickup.requested",
    "pickup.cancelled",
    "delivery.scheduled",
    "delivery.dispatched",
    "delivery.delivered",
    "delivery.cancelled",
    "heap.opened",
    "heap.closed",
    "bale.created",
    "bale.voided",
    "qr.scanned",
    # Module 8 (Settings)
    "config.changed",
    "officer.created",
    "officer.updated",
    "officer.deactivated",
    "list.changed",
    "location.changed",
    "backup.created",
    "backup.restored",
}


def test_known_events_match_contract() -> None:
    assert KNOWN_EVENTS == EXPECTED_EVENTS


def test_publish_calls_subscribers_in_order() -> None:
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe(FARMER_REGISTERED, lambda e: calls.append(f"a:{e.payload['id']}"))
    bus.subscribe(FARMER_REGISTERED, lambda e: calls.append(f"b:{e.payload['id']}"))
    bus.subscribe(FIELD_CREATED, lambda e: calls.append("wrong"))
    event = bus.publish(FARMER_REGISTERED, {"id": "f1"}, officer_id="o1")
    assert calls == ["a:f1", "b:f1"]
    assert event.officer_id == "o1"
    assert event.occurred_at.tzinfo is not None


def test_subscribe_is_idempotent_and_unsubscribe() -> None:
    bus = EventBus()
    calls: list[Event] = []
    handler = calls.append
    bus.subscribe(FIELD_CREATED, handler)
    bus.subscribe(FIELD_CREATED, handler)
    bus.publish(FIELD_CREATED, {})
    assert len(calls) == 1
    bus.unsubscribe(FIELD_CREATED, handler)
    bus.publish(FIELD_CREATED, {})
    assert len(calls) == 1


def test_handler_failure_is_logged_others_still_run_then_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus = EventBus()
    ran: list[str] = []

    def broken(_e: Event) -> None:
        raise RuntimeError("handler exploded")

    bus.subscribe(FIELD_CREATED, broken)
    bus.subscribe(FIELD_CREATED, lambda e: ran.append("second"))
    with (
        caplog.at_level(logging.ERROR, logger="sawie.events"),
        pytest.raises(EventHandlerError) as info,
    ):
        bus.publish(FIELD_CREATED, {"field_id": "x"})
    assert ran == ["second"]
    assert info.value.event_name == FIELD_CREATED
    assert len(info.value.failures) == 1
    assert "handler exploded" in caplog.text
    assert any(r.exc_info for r in caplog.records)


def test_capture_hook_records_events() -> None:
    bus = EventBus()
    with bus.capture() as captured:
        bus.publish(FARMER_REGISTERED, {"id": "1"})
        bus.publish(FIELD_CREATED, {"id": "2"})
    bus.publish(FIELD_CREATED, {"id": "3"})
    assert [e.name for e in captured] == [FARMER_REGISTERED, FIELD_CREATED]


def test_unknown_event_names_are_rejected() -> None:
    bus = EventBus()
    with pytest.raises(UnknownEventError):
        bus.publish("farmer.typo", {})
    with pytest.raises(UnknownEventError):
        bus.subscribe("nope", lambda e: None)
