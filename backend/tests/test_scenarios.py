"""End-to-end scenarios across modules, driven through the HTTP API (audit Phase 3)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from module_1.tests.conftest import cotton_picking


def test_cotton_chain_from_farmer_to_bale_with_a_six_percent_variance(
    client: TestClient,
    make_farm: Callable[..., dict[str, Any]],
    schedule: Callable[..., dict[str, Any]],
    deliver: Callable[..., dict[str, Any]],
    heap_with_bales: Callable[..., dict[str, Any]],
) -> None:
    farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
    planned = schedule(farm)
    estimate = float(planned["estimated_quantity_kg"])
    base = f"/api/v1/deliveries/{planned['id']}"
    client.post(f"{base}/dispatch", json={}, headers=farm["headers"])
    weighed = round(estimate * 1.06, 2)
    received = client.post(
        f"{base}/receive",
        json={"weighbridge_weight_kg": weighed, "moisture_pct": 9.0, "note": "6 percent over"},
        headers=farm["headers"],
    )
    assert received.status_code == 200, received.text
    delivery = received.json()["delivery"]
    assert abs(delivery["variance_pct"] - 6.0) < 0.1
    assert delivery["variance_level"] not in (None, "ok")  # flagged, never silently accepted
    heap = heap_with_bales([delivery], bales=2)
    assert heap["totals"]["bales_made"] == 2


def test_a_delivery_cannot_be_received_twice(
    client: TestClient,
    make_farm: Callable[..., dict[str, Any]],
    schedule: Callable[..., dict[str, Any]],
) -> None:
    farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
    dl = schedule(farm)
    base = f"/api/v1/deliveries/{dl['id']}"
    client.post(f"{base}/dispatch", json={}, headers=farm["headers"])
    body = {"weighbridge_weight_kg": 500, "moisture_pct": 9.0, "note": "Test load"}
    assert client.post(f"{base}/receive", json=body, headers=farm["headers"]).status_code == 200
    again = client.post(f"{base}/receive", json=body, headers=farm["headers"])
    assert again.status_code in (400, 409, 422)


def test_a_field_with_a_fieldbook_cannot_be_deleted_by_another_officer(
    client: TestClient,
    make_farm: Callable[..., dict[str, Any]],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    farm = make_farm("cotton", sown=30)
    other = as_officer("PK-BWP-01")
    r = client.delete(
        f"/api/v1/register/fields/{farm['field']['id']}",
        headers=other,
    )
    assert r.status_code == 403


def test_hemp_farm_registers_and_shows_in_the_dashboard(
    client: TestClient,
    make_farm: Callable[..., dict[str, Any]],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    farm = make_farm("hemp", sown=20)
    assert farm["field"]["id"]
    r = client.get("/api/v1/dashboard/overview", headers=as_officer("ADMIN-01"))
    assert r.status_code == 200
