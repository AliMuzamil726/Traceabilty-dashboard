"""Events published by Module 3 and the guards it adds to Module 2's field actions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from core.events import bus
from module_3.tests.conftest import FB, MULTAN, REG, cotton_steps, square

Farm = dict[str, Any]


def test_step_saved_is_published(
    client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    with bus.capture() as events:
        client.put(
            f"{FB}/books/{book['id']}/steps/energy",
            json={"data": cotton_steps()["energy"]},
            headers=farm["headers"],
        )
    saved = [e for e in events if e.name == "fieldbook.step_saved"]
    assert len(saved) == 1
    assert saved[0].payload["step_key"] == "energy"
    assert saved[0].payload["fieldbook_id"] == book["id"]


def test_ready_for_pickup_fires_once_on_the_change_to_yes(
    client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    url = f"{FB}/books/{book['id']}/steps/harvest/entries"
    entry = cotton_steps()["harvest"][0]
    client.put(
        f"{FB}/books/{book['id']}/steps/field_info",
        json={"data": cotton_steps()["field_info"]},
        headers=farm["headers"],
    )
    with bus.capture() as events:
        client.post(url, json={"data": dict(entry, ready_for_pickup="no")}, headers=farm["headers"])
        client.put(f"{url}/0", json={"data": entry}, headers=farm["headers"])
        client.put(f"{url}/0", json={"data": dict(entry, moisture=8)}, headers=farm["headers"])
    ready = [e for e in events if e.name == "fieldbook.ready_for_pickup"]
    assert len(ready) == 1
    assert ready[0].payload["picking_number"] == "1st"
    assert ready[0].payload["estimated_kg"] == 12 * 9.5 * 40


def test_submitted_is_published(
    client: TestClient,
    make_farm: Callable[..., Farm],
    open_book: Callable[..., Farm],
    fill: Callable[..., Farm],
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    fill(book, farm["headers"], cotton_steps())
    with bus.capture() as events:
        client.post(f"{FB}/books/{book['id']}/submit", headers=farm["headers"])
    assert [e.name for e in events if e.name == "fieldbook.submitted"] == ["fieldbook.submitted"]


def test_a_draft_does_not_block_module_2(
    client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    fid = farm["field"]["id"]
    moved = client.put(
        f"{REG}/fields/{fid}",
        json={"geometry": square((MULTAN[0] + 0.5, MULTAN[1]), 200)},
        headers=farm["headers"],
    )
    assert moved.status_code == 200, moved.text
    assert client.delete(f"{REG}/fields/{fid}", headers=farm["headers"]).status_code == 204
    # The draft follows the field away.
    assert client.get(f"{FB}/books/{book['id']}", headers=farm["headers"]).status_code == 404


def test_a_submitted_book_locks_the_field_in_module_2(
    client: TestClient,
    make_farm: Callable[..., Farm],
    open_book: Callable[..., Farm],
    fill: Callable[..., Farm],
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    fill(book, farm["headers"], cotton_steps())
    client.post(f"{FB}/books/{book['id']}/submit", headers=farm["headers"])
    fid = farm["field"]["id"]
    moved = client.put(
        f"{REG}/fields/{fid}",
        json={"geometry": square((MULTAN[0] + 0.5, MULTAN[1]), 200)},
        headers=farm["headers"],
    )
    assert moved.status_code == 409
    assert moved.json()["error"]["code"] == "field_has_fieldbook"
    gone = client.delete(f"{REG}/fields/{fid}", headers=farm["headers"])
    assert gone.status_code == 409
    assert gone.json()["error"]["code"] == "field_has_fieldbook"
