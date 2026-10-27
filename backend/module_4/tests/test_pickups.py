"""Pickup requests: bulk partial success, one open request, scoping, cancelling, guard,
events, concurrency and the public API Module 5 will use."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.deps import CurrentOfficer
from core.events import bus
from module_4 import public_api as api
from module_4.services.pickups import PickupService
from module_4.tests.conftest import RADAR, REG, cotton_picking, row_for

Farm = dict[str, Any]
YEAR = date.today().year


def request(
    client: TestClient, headers: dict[str, str], *farms: Farm, crop: str = "cotton", **extra: Any
) -> Any:
    return client.post(
        f"{RADAR}/pickup-requests",
        headers=headers,
        json={
            "crop": crop,
            "season_year": YEAR,
            "field_ids": [f["field"]["id"] for f in farms],
            **extra,
        },
    )


def test_bulk_request_creates_eligible_and_skips_the_rest(
    client: TestClient, make_farm: Callable[..., Farm], as_officer: Callable[[str], dict[str, str]]
) -> None:
    ready = make_farm(sown=140)
    harvested = make_farm(sown=150, harvest=cotton_picking())
    growing = make_farm(sown=20)
    unsown = make_farm()
    someone_elses = make_farm(sown=140, officer="PK-BWP-01")
    me = as_officer("PK-MUL-01")
    r = request(
        client,
        me,
        ready,
        harvested,
        growing,
        unsown,
        someone_elses,
        preferred_date=(date.today() + timedelta(days=3)).isoformat(),
        note="Gate on the east side",
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert [c["field_id"] for c in body["created"]] == [
        ready["field"]["id"],
        harvested["field"]["id"],
    ]
    assert [c["request_no"] for c in body["created"]] == ["PR-0001", "PR-0002"]
    first = body["created"][0]
    assert first["status"] == "requested"
    assert first["note"] == "Gate on the east side"
    assert first["quantity_is_estimate"] is True
    assert first["estimated_quantity_kg"] > 0
    reasons = {s["field_id"]: s["code"] for s in body["skipped"]}
    assert reasons == {
        growing["field"]["id"]: "pickup_not_ready",
        unsown["field"]["id"]: "pickup_not_ready",
        someone_elses["field"]["id"]: "pickup_forbidden",
    }
    assert all(s["reason"] for s in body["skipped"])


def test_duplicates_are_impossible(
    client: TestClient, make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]]
) -> None:
    farm = make_farm(sown=140)
    assert len(request(client, farm["headers"], farm).json()["created"]) == 1
    again = request(client, farm["headers"], farm, farm).json()
    assert again["created"] == []
    assert [s["code"] for s in again["skipped"]] == ["pickup_already_open"]
    row = row_for(radar(farm["headers"]), farm)
    assert (row["pickup_state"], row["request_no"], row["can_request"]) == (
        "requested",
        "PR-0001",
        False,
    )
    page = radar(farm["headers"])
    assert page["kpis"]["pickup_requested"]["fields"] == 1
    assert radar(farm["headers"], pickup="requested")["total"] == 1


def test_one_open_request_under_concurrency(
    client: TestClient, make_farm: Callable[..., Farm], officer_ids: dict[str, str]
) -> None:
    farm = make_farm(sown=140)
    db = client.app.state.db  # type: ignore[attr-defined]
    officer = CurrentOfficer(
        id=officer_ids["PK-MUL-01"],
        code="PK-MUL-01",
        full_name="x",
        role="officer",
        country="PK",
        field_office_id=None,
        field_office_name=None,
    )
    threads, created, errors = 12, [], []
    lock, start = threading.Lock(), threading.Barrier(threads)

    def worker() -> None:
        session = db.session_factory()
        try:
            start.wait(timeout=30)
            made, _ = PickupService(session).request(
                officer, crop="cotton", season_year=YEAR, field_ids=[farm["field"]["id"]]
            )
            with lock:
                created.extend(m.request_no for m in made)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)
        finally:
            session.close()

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    assert errors == []
    assert len(created) == 1


def test_the_database_refuses_a_second_open_request(
    client: TestClient, make_farm: Callable[..., Farm]
) -> None:
    from sqlalchemy.exc import IntegrityError

    from module_4.models import PickupRequest

    farm = make_farm(sown=140)
    request(client, farm["headers"], farm)
    db = client.app.state.db  # type: ignore[attr-defined]
    session = db.session_factory()
    try:
        session.add(
            PickupRequest(
                request_no="PR-9999",
                field_id=farm["field"]["id"],
                field_code="x",
                farmer_id="x",
                crop="cotton",
                season_year=YEAR,
                status="scheduled",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_cancel_rules(
    client: TestClient,
    make_farm: Callable[..., Farm],
    as_officer: Callable[[str], dict[str, str]],
    radar: Callable[..., dict[str, Any]],
) -> None:
    farm = make_farm(sown=140)
    req = request(client, farm["headers"], farm).json()["created"][0]
    url = f"{RADAR}/pickup-requests/{req['id']}/cancel"
    assert client.post(url, json={"reason": "  "}, headers=farm["headers"]).status_code == 422
    assert (
        client.post(url, json={"reason": "No"}, headers=as_officer("PK-BWP-01")).status_code == 403
    )
    done = client.post(
        url, json={"reason": "Farmer sold to a local ginner"}, headers=farm["headers"]
    )
    assert done.status_code == 200
    assert (done.json()["status"], done.json()["cancel_reason"]) == (
        "cancelled",
        "Farmer sold to a local ginner",
    )
    again = client.post(url, json={"reason": "again"}, headers=farm["headers"])
    assert (again.status_code, again.json()["error"]["code"]) == (409, "pickup_not_cancellable")
    assert row_for(radar(farm["headers"]), farm)["pickup_state"] == "not_requested"
    # A cancelled request frees the field for a new one.
    assert request(client, farm["headers"], farm).json()["created"][0]["request_no"] == "PR-0002"


def test_scheduled_requests_cannot_be_cancelled_by_officers(
    client: TestClient, make_farm: Callable[..., Farm]
) -> None:
    farm = make_farm(sown=140)
    req = request(client, farm["headers"], farm).json()["created"][0]
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session_scope() as session:
        api.mark_pickup_scheduled(session, req["id"], "delivery-1")
    r = client.post(
        f"{RADAR}/pickup-requests/{req['id']}/cancel", json={"reason": "x"}, headers=farm["headers"]
    )
    assert r.status_code == 409


def test_listing_is_scoped(
    client: TestClient, make_farm: Callable[..., Farm], as_officer: Callable[[str], dict[str, str]]
) -> None:
    mine = make_farm(sown=140)
    theirs = make_farm(sown=140, officer="PK-BWP-01")
    request(client, mine["headers"], mine)
    request(client, theirs["headers"], theirs)
    own = client.get(f"{RADAR}/pickup-requests", headers=mine["headers"]).json()
    assert [r["field_id"] for r in own["items"]] == [mine["field"]["id"]]
    assert own["items"][0]["can_cancel"] is True
    assert own["items"][0]["farmer_name"] == mine["farmer"]["name"]
    every = client.get(f"{RADAR}/pickup-requests", headers=as_officer("ADMIN-01")).json()
    assert every["total"] == 2
    cancelled = client.get(
        f"{RADAR}/pickup-requests", params={"status": "cancelled"}, headers=as_officer("ADMIN-01")
    ).json()
    assert cancelled["total"] == 0


def test_events_are_published(client: TestClient, make_farm: Callable[..., Farm]) -> None:
    farm = make_farm(sown=140)
    with bus.capture() as seen:
        req = request(client, farm["headers"], farm).json()["created"][0]
        client.post(
            f"{RADAR}/pickup-requests/{req['id']}/cancel",
            json={"reason": "Wet weather"},
            headers=farm["headers"],
        )
    names = [e.name for e in seen if e.name.startswith("pickup.")]
    assert names == ["pickup.requested", "pickup.cancelled"]
    payload = next(e.payload for e in seen if e.name == "pickup.requested")
    assert payload["request_no"] == "PR-0001"
    assert payload["field_id"] == farm["field"]["id"]
    assert next(e.payload for e in seen if e.name == "pickup.cancelled")["reason"] == "Wet weather"


def test_an_open_request_blocks_deleting_the_field(
    client: TestClient, make_farm: Callable[..., Farm]
) -> None:
    farm = make_farm(sown=140)
    req = request(client, farm["headers"], farm).json()["created"][0]
    blocked = client.delete(f"{REG}/fields/{farm['field']['id']}", headers=farm["headers"])
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "field_has_pickup_request"
    client.post(
        f"{RADAR}/pickup-requests/{req['id']}/cancel", json={"reason": "x"}, headers=farm["headers"]
    )
    assert (
        client.delete(f"{REG}/fields/{farm['field']['id']}", headers=farm["headers"]).status_code
        == 204
    )


def test_field_deleted_event_cancels_open_requests(
    client: TestClient, make_farm: Callable[..., Farm]
) -> None:
    """An administrator override that removes the field anyway closes its requests."""
    from core import events

    farm = make_farm(sown=140)
    req = request(client, farm["headers"], farm).json()["created"][0]
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session_scope() as session:
        bus.publish(
            events.FIELD_DELETED,
            {"field_id": farm["field"]["id"], "field_code": "x", "farmer_id": farm["farmer"]["id"]},
            session=session,
        )
    with db.session_scope() as session:
        dto = api.get_pickup_request(session, req["id"])
    assert dto is not None
    assert (dto.status, dto.cancel_reason) == (
        "cancelled",
        "The field was removed in Register Farmer.",
    )


def test_public_api_for_module_5(client: TestClient, make_farm: Callable[..., Farm]) -> None:
    a, b = make_farm(sown=140), make_farm(sown=150, harvest=cotton_picking())
    created = request(client, a["headers"], a, b).json()["created"]
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session_scope() as session:
        open_ = api.list_open_pickup_requests(session, crop="cotton")
        assert [r.request_no for r in open_] == ["PR-0001", "PR-0002"]
        scheduled = api.mark_pickup_scheduled(session, created[0]["id"], "delivery-77")
        assert (scheduled.status, scheduled.delivery_id) == ("scheduled", "delivery-77")
        assert api.mark_pickup_fulfilled(session, created[0]["id"]).status == "fulfilled"
        assert (
            api.mark_pickup_cancelled(session, created[1]["id"], "Ginner closed").status
            == "cancelled"
        )
        assert api.list_open_pickup_requests(session) == []
    with db.session_scope() as session:
        readiness = api.get_field_readiness(session, a["field"]["id"], YEAR)
        assert readiness is not None
        assert (readiness.status, readiness.pickup_state) == ("ready", "delivered")
        assert api.get_field_readiness(session, "nope") is None
        counts = api.count_fields_by_status(session, api.RadarQuery(crop="cotton"))
        assert counts == {
            "no_sowing_data": 0,
            "growing": 0,
            "approaching": 0,
            "ready": 1,
            "harvested": 1,
        }
        summary = api.get_radar_summary(session)
        assert summary.ready_now.fields == 1
        assert summary.area_unit == "acre"
