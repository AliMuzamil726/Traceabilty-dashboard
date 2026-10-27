"""Events, guards, the Radar sync and the heap-assignment API Module 6 will use."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core import events
from core.errors import AppError
from core.events import bus
from core.guards import DELIVERY_CAN_UNASSIGN, GuardResult, guards
from module_5 import public_api as api
from module_5.tests.conftest import DL, RADAR, REG, square

Farm = dict[str, Any]


def test_every_transition_publishes_its_event(
    client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
) -> None:
    farm = make_request()
    h = farm["headers"]
    with bus.capture() as seen:
        dl = schedule(farm)
        client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=h)
        client.post(
            f"{DL}/{dl['id']}/receive",
            json={"weighbridge_weight_kg": 7900, "moisture_pct": 9},
            headers=h,
        )
    names = [e.name for e in seen if e.name.startswith("delivery.")]
    assert names == ["delivery.scheduled", "delivery.dispatched", "delivery.delivered"]
    delivered = next(e for e in seen if e.name == "delivery.delivered").payload
    assert (delivered["delivery_no"], delivered["weighbridge_weight_kg"]) == ("DL-0001", 7900)
    second = make_request()
    other = schedule(second)
    with bus.capture() as seen:
        client.post(f"{DL}/{other['id']}/cancel", json={"reason": "Driver unavailable"}, headers=h)
    assert [e.name for e in seen if e.name in ("delivery.cancelled", "pickup.cancelled")] == [
        "delivery.cancelled",
        "pickup.cancelled",
    ]


def test_cancelling_the_radar_request_cancels_the_delivery(
    client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
) -> None:
    from module_4 import public_api as radar

    farm = make_request()
    dl = schedule(farm)
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session_scope() as s:
        radar.mark_pickup_cancelled(s, farm["request"]["id"], "Farmer sold elsewhere")
    got = client.get(f"{DL}/{dl['id']}", headers=farm["headers"]).json()
    assert got["status"] == "cancelled"
    assert "was cancelled" in got["cancel_reason"]


def test_any_live_delivery_blocks_field_changes(
    client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
) -> None:
    farm = make_request()
    dl = schedule(farm)
    h = farm["headers"]
    fid = farm["field"]["id"]
    client.post(f"{DL}/{dl['id']}/cancel", json={"reason": "Wrong lorry"}, headers=h)
    # The request is closed, so only the delivery guard matters from here.
    reshaped = client.put(f"{REG}/fields/{fid}", json={"geometry": square((30.9, 71.9))}, headers=h)
    assert reshaped.status_code == 200, reshaped.text  # a cancelled delivery does not block
    again = client.post(
        f"{RADAR}/pickup-requests",
        headers=h,
        json={"crop": "cotton", "season_year": farm["request"]["season_year"], "field_ids": [fid]},
    ).json()
    farm["request"] = again["created"][0]
    schedule(farm)
    moved = client.put(f"{REG}/fields/{fid}", json={"geometry": square((31.2, 71.9))}, headers=h)
    assert (moved.status_code, moved.json()["error"]["code"]) == (409, "field_has_delivery")
    gone = client.delete(f"{REG}/fields/{fid}", headers=h)
    assert gone.status_code == 409
    codes = {r["code"] for r in gone.json()["error"]["details"]["reasons"]}
    assert "field_has_delivery" in codes


def test_field_deleted_event_cancels_moving_deliveries(
    client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
) -> None:
    farm = make_request()
    dl = schedule(farm)
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session_scope() as s:
        bus.publish(
            events.FIELD_DELETED,
            {"field_id": farm["field"]["id"], "field_code": "x", "farmer_id": farm["farmer"]["id"]},
            session=s,
        )
    got = client.get(f"{DL}/{dl['id']}", headers=farm["headers"]).json()
    # Radar's handler runs first and closes the request, which cancels the delivery.
    assert got["status"] == "cancelled"
    assert got["cancel_reason"]


class TestHeapAssignment:
    def test_rules(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        deliver: Callable[..., Any],
        schedule: Callable[..., Any],
        sites: dict[str, str],
    ) -> None:
        good = deliver(make_request(), site="BWP-G1")
        elsewhere = deliver(make_request(), site="BWP-G2")
        moving = schedule(make_request())
        db = client.app.state.db  # type: ignore[attr-defined]
        site = sites["BWP-G1"]
        with db.session_scope() as s:
            assert [x.id for x in api.list_delivered_unassigned(s, site, "cotton")] == [good["id"]]
            for delivery_id, crop, code in (
                (elsewhere["id"], "cotton", "delivery_wrong_site"),
                (good["id"], "hemp", "delivery_wrong_crop"),
                (moving["id"], "cotton", "delivery_not_delivered"),
            ):
                with pytest.raises(AppError) as err:
                    api.assign_heap(s, delivery_id, "BWP-G1-H01", None, site_id=site, crop=crop)
                assert err.value.code == code
            dto = api.assign_heap(s, good["id"], "BWP-G1-H01", None, site_id=site, crop="cotton")
            assert dto.heap_id == "BWP-G1-H01"
        with db.session_scope() as s:
            with pytest.raises(AppError) as err:
                api.assign_heap(s, good["id"], "BWP-G1-H02", None, site_id=site, crop="cotton")
            assert err.value.code == "delivery_already_assigned"
            assert [x.id for x in api.list_by_heap(s, "BWP-G1-H01")] == [good["id"]]
            assert api.list_delivered_unassigned(s, site, "cotton") == []
            summary = api.get_farmer_delivery_summary(s, good["farmer_id"])
            assert (summary.delivered, summary.heaps) == (1, ["BWP-G1-H01"])
        detail = client.get(f"{DL}/{good['id']}", headers={}).json()
        assert detail["heap_id"] == "BWP-G1-H01"

    def test_unassign_asks_the_guard(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        deliver: Callable[..., Any],
        sites: dict[str, str],
    ) -> None:
        good = deliver(make_request())
        db = client.app.state.db  # type: ignore[attr-defined]
        with db.session_scope() as s:
            api.assign_heap(
                s, good["id"], "BWP-G1-H09", None, site_id=sites["BWP-G1"], crop="cotton"
            )

        def deny(**_: Any) -> GuardResult:
            return GuardResult.deny("heap_has_bales", "The heap already has bales.")

        guards.register(DELIVERY_CAN_UNASSIGN, deny, owner="test")
        try:
            with db.session_scope() as s, pytest.raises(AppError) as err:
                api.unassign_heap(s, good["id"], None, "Wrong heap")
            assert err.value.status_code == 409
        finally:
            guards._checks[DELIVERY_CAN_UNASSIGN].remove(("test", deny))
        with db.session_scope() as s:
            with pytest.raises(AppError):
                api.unassign_heap(s, good["id"], None, " ")
            assert api.unassign_heap(s, good["id"], None, "Wrong heap").heap_id is None

    def test_stats_dto(
        self, client: TestClient, make_request: Callable[..., Farm], deliver: Callable[..., Any]
    ) -> None:
        deliver(make_request(), weighbridge=4000)
        db = client.app.state.db  # type: ignore[attr-defined]
        with db.session_scope() as s:
            stats = api.get_delivery_stats(s, api.DeliveryQuery(crop="cotton"))
            assert (
                stats.total,
                stats.by_status["delivered"],
                stats.delivered_kg,
                stats.delivered_maunds,
            ) == (1, 1, 4000, 100)
