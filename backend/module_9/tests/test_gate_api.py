"""Gate Reception API: arrival, accept, reject, reconciliation with Deliveries, figures."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from module_9.tests.conftest import DL, GATE, arrive

Json = dict[str, Any]


def code(response: Any) -> str:
    return str(response.json()["error"]["code"])


def test_meta(client: TestClient) -> None:
    body = client.get(f"{GATE}/meta").json()
    assert body == {
        "number": 9,
        "name": "Gate Reception",
        "route_prefix": "/gate",
        "api_prefix": "/api/v1/gate",
        "status": "active",
        "build_order": 9,
        "purpose": (
            "Record the arrival of in-transit deliveries at the ginner or processor gate: "
            "weighbridge reading, moisture check, vehicle inspection and officer sign-off."
        ),
    }


def test_inbound_lists_only_loads_in_transit_without_an_entry(
    client: TestClient,
    sites: dict[str, str],
    make_request: Callable[..., Json],
    schedule: Callable[..., Json],
    in_transit: Callable[..., Json],
) -> None:
    scheduled_farm = make_request("cotton")
    schedule(scheduled_farm)
    moving_farm = make_request("cotton")
    moving = in_transit(moving_farm)

    r = client.get(f"{GATE}/inbound", params={"site_id": sites["BWP-G1"]})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["delivery_id"] for row in rows] == [moving["id"]]
    assert rows[0]["driver_name"] == moving["driver_name"]
    assert rows[0]["field_code"] == moving["field_code"]
    assert rows[0]["farmer_name"] is not None

    arrive(client, moving, moving_farm["headers"])
    assert client.get(f"{GATE}/inbound", params={"site_id": sites["BWP-G1"]}).json() == []
    # The other site sees nothing.
    assert client.get(f"{GATE}/inbound", params={"site_id": sites["UK-P1"]}).json() == []


def test_arrival_copies_the_transport_and_refuses_a_duplicate(
    client: TestClient,
    sites: dict[str, str],
    make_request: Callable[..., Json],
    schedule: Callable[..., Json],
    in_transit: Callable[..., Json],
) -> None:
    farm = make_request("cotton")
    delivery = in_transit(farm)
    entry = arrive(client, delivery, farm["headers"])
    assert entry["status"] == "pending"
    assert entry["delivery_id"] == delivery["id"]
    assert entry["delivery_no"] == delivery["delivery_no"]
    assert entry["site_id"] == sites["BWP-G1"]
    assert entry["vehicle_no"] == delivery["vehicle_no"]
    assert entry["driver_name"] == delivery["driver_name"]
    assert entry["can_accept"]
    assert entry["can_reject"]
    assert entry["site_code"] == "BWP-G1"

    again = client.post(
        f"{GATE}/entries", json={"delivery_id": delivery["id"]}, headers=farm["headers"]
    )
    assert again.status_code == 409
    assert code(again) == "gate_entry_exists"

    # A scheduled load has not left the farm, so it cannot be at the gate.
    other = make_request("cotton")
    waiting = schedule(other)
    refused = client.post(
        f"{GATE}/entries", json={"delivery_id": waiting["id"]}, headers=other["headers"]
    )
    assert refused.status_code == 422
    assert code(refused) == "gate_delivery_not_in_transit"


def test_accept_receives_the_delivery_with_the_net_weight(
    client: TestClient,
    make_request: Callable[..., Json],
    in_transit: Callable[..., Json],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    farm = make_request("cotton")
    delivery = in_transit(farm)
    entry = arrive(client, delivery, farm["headers"])

    # The gate officer need not be the officer who registered the farmer.
    gate_headers = as_officer("PK-MUL-02")
    r = client.post(
        f"{GATE}/entries/{entry['id']}/accept",
        json={
            "gross_weight_kg": 5_000,
            "tare_weight_kg": 1_000,
            "moisture_pct": 9,
            "note": "Clean load",
        },
        headers=gate_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entry"]["status"] == "accepted"
    assert body["entry"]["net_weight_kg"] == 4_000
    assert body["entry"]["gross_weight_kg"] == 5_000
    assert body["entry"]["tare_weight_kg"] == 1_000
    assert body["entry"]["accepted_at"] is not None
    assert body["entry"]["can_accept"] is False

    detail = client.get(f"{DL}/{delivery['id']}", headers=farm["headers"]).json()
    assert detail["status"] == "delivered"
    assert detail["weighbridge_weight_kg"] == 4_000
    assert detail["moisture_pct"] == 9

    twice = client.post(
        f"{GATE}/entries/{entry['id']}/accept",
        json={"gross_weight_kg": 5_000, "tare_weight_kg": 1_000, "moisture_pct": 9},
        headers=gate_headers,
    )
    assert twice.status_code == 409
    assert code(twice) == "invalid_gate_status"


def test_accept_refuses_a_gross_weight_at_or_below_the_tare(
    client: TestClient,
    make_request: Callable[..., Json],
    in_transit: Callable[..., Json],
) -> None:
    farm = make_request("cotton")
    delivery = in_transit(farm)
    entry = arrive(client, delivery, farm["headers"])
    r = client.post(
        f"{GATE}/entries/{entry['id']}/accept",
        json={"gross_weight_kg": 1_000, "tare_weight_kg": 1_000, "moisture_pct": 9},
        headers=farm["headers"],
    )
    assert r.status_code == 422
    assert code(r) == "gate_weight_invalid"
    assert client.get(f"{GATE}/entries/{entry['id']}").json()["status"] == "pending"


def test_reject_cancels_the_delivery_with_the_reason(
    client: TestClient,
    make_request: Callable[..., Json],
    in_transit: Callable[..., Json],
) -> None:
    farm = make_request("cotton")
    delivery = in_transit(farm)
    entry = arrive(client, delivery, farm["headers"])
    r = client.post(
        f"{GATE}/entries/{entry['id']}/reject",
        json={"rejection_reason": "Wrong vehicle for this load."},
        headers=farm["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Wrong vehicle for this load."
    assert body["rejected_at"] is not None

    detail = client.get(f"{DL}/{delivery['id']}", headers=farm["headers"]).json()
    assert detail["status"] == "cancelled"
    assert detail["cancel_reason"] == "Wrong vehicle for this load."


def test_receiving_in_deliveries_closes_the_pending_gate_entry(
    client: TestClient,
    make_request: Callable[..., Json],
    in_transit: Callable[..., Json],
) -> None:
    farm = make_request("cotton")
    delivery = in_transit(farm)
    entry = arrive(client, delivery, farm["headers"])
    weight = delivery["estimated_quantity_kg"] or 1_000
    r = client.post(
        f"{DL}/{delivery['id']}/receive",
        json={"weighbridge_weight_kg": weight, "moisture_pct": 9},
        headers=farm["headers"],
    )
    assert r.status_code == 200, r.text

    closed = client.get(f"{GATE}/entries/{entry['id']}").json()
    assert closed["status"] == "accepted"
    assert closed["net_weight_kg"] == weight
    assert closed["moisture_pct"] == 9
    assert closed["note"] == "Received in Deliveries."


def test_cancelling_in_deliveries_rejects_the_pending_gate_entry(
    client: TestClient,
    make_request: Callable[..., Json],
    in_transit: Callable[..., Json],
) -> None:
    farm = make_request("cotton")
    delivery = in_transit(farm)
    entry = arrive(client, delivery, farm["headers"])
    r = client.post(
        f"{DL}/{delivery['id']}/cancel",
        json={"reason": "Driver turned back."},
        headers=farm["headers"],
    )
    assert r.status_code == 200, r.text

    closed = client.get(f"{GATE}/entries/{entry['id']}").json()
    assert closed["status"] == "rejected"
    assert closed["rejection_reason"] == "Delivery cancelled: Driver turned back."


def test_correcting_a_delivery_updates_the_accepted_gate_entry(
    client: TestClient,
    make_request: Callable[..., Json],
    in_transit: Callable[..., Json],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    farm = make_request("cotton")
    delivery = in_transit(farm)
    entry = arrive(client, delivery, farm["headers"])
    accepted = client.post(
        f"{GATE}/entries/{entry['id']}/accept",
        json={
            "gross_weight_kg": 5_000,
            "tare_weight_kg": 1_000,
            "moisture_pct": 9,
            "note": "Clean load",
        },
        headers=farm["headers"],
    )
    assert accepted.status_code == 200, accepted.text

    fixed = client.post(
        f"{DL}/{delivery['id']}/correct",
        json={"reason": "Ticket misread", "weighbridge_weight_kg": 4_250, "moisture_pct": 10},
        headers=as_officer("ADMIN-01"),
    )
    assert fixed.status_code == 200, fixed.text

    updated = client.get(f"{GATE}/entries/{entry['id']}").json()
    assert (updated["net_weight_kg"], updated["moisture_pct"]) == (4_250, 10)
    assert "Corrected in Deliveries: Ticket misread" in updated["note"]


def test_summary_counts_inbound_pending_accepted_and_rejected(
    client: TestClient,
    sites: dict[str, str],
    make_request: Callable[..., Json],
    in_transit: Callable[..., Json],
) -> None:
    accepted_farm = make_request("cotton")
    accepted = in_transit(accepted_farm)
    accepted_entry = arrive(client, accepted, accepted_farm["headers"])
    client.post(
        f"{GATE}/entries/{accepted_entry['id']}/accept",
        json={
            "gross_weight_kg": 5_000,
            "tare_weight_kg": 1_000,
            "moisture_pct": 9,
            "note": "Weighed over the bridge.",
        },
        headers=accepted_farm["headers"],
    )

    pending_farm = make_request("cotton")
    pending = in_transit(pending_farm)
    arrive(client, pending, pending_farm["headers"])

    rejected_farm = make_request("cotton")
    rejected = in_transit(rejected_farm)
    rejected_entry = arrive(client, rejected, rejected_farm["headers"])
    client.post(
        f"{GATE}/entries/{rejected_entry['id']}/reject",
        json={"rejection_reason": "Load refused at the gate."},
        headers=rejected_farm["headers"],
    )

    inbound_farm = make_request("cotton")
    in_transit(inbound_farm)

    body = client.get(f"{GATE}/summary", params={"site_id": sites["BWP-G1"]}).json()
    assert body == {
        "inbound": 1,
        "pending": 1,
        "accepted_today": 1,
        "rejected_today": 1,
        "net_kg_today": 4_000,
    }

    entries = client.get(f"{GATE}/entries", params={"site_id": sites["BWP-G1"]}).json()
    assert entries["total"] == 3
    assert {row["status"] for row in entries["items"]} == {"accepted", "pending", "rejected"}

    pending_only = client.get(
        f"{GATE}/entries", params={"site_id": sites["BWP-G1"], "status": "pending"}
    ).json()
    assert pending_only["total"] == 1
    assert [row["status"] for row in pending_only["items"]] == ["pending"]

    decided = client.get(
        f"{GATE}/entries", params={"site_id": sites["BWP-G1"], "status": "decided"}
    ).json()
    assert decided["total"] == 2
    assert {row["status"] for row in decided["items"]} == {"accepted", "rejected"}
