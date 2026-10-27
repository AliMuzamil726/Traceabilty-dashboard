"""Heaps API: opening, assignment rules, bales, the bale limit under concurrency,
closing, locking, contributions, guards, events and audit."""

from __future__ import annotations

import threading
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.deps import CurrentOfficer
from core.events import bus
from module_6 import public_api as api
from module_6.services.heaps import HeapService
from module_6.tests.conftest import DL, HEAPS

Json = dict[str, Any]


def add(
    client: TestClient, heap: Json, *deliveries: Json, headers: dict[str, str] | None = None
) -> Json:
    r = client.post(
        f"{HEAPS}/{heap['id']}/deliveries",
        json={"delivery_ids": [d["id"] for d in deliveries]},
        headers=headers or {},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_open_heap_ids_per_site_and_wording(
    client: TestClient, open_heap: Callable[..., Json], sites: dict[str, str]
) -> None:
    first = open_heap("BWP-G1")
    assert first["heap_id"] == "BWP-G1-H01"
    assert (first["outturn_ratio_pct"], first["bale_unit_kg"], first["shiv_pct"]) == (
        34.0,
        170.0,
        None,
    )
    second = client.post(HEAPS, json={"site_id": sites["BWP-G1"]}).json()
    assert second["heap"]["heap_id"] == "BWP-G1-H02"
    assert second["warnings"] == ["BWP-G1-H01 is already open at Bahawalpur Ginner 1 (dummy)."]
    assert open_heap("MUX-G1")["heap_id"] == "MUX-G1-H01"
    batch = open_heap("UK-P1", officer="GB-EOE-01")
    assert batch["heap_id"] == "UK-P1-BT01"
    assert (batch["crop"], batch["outturn_ratio_pct"], batch["bale_unit_kg"]) == (
        "hemp",
        25.0,
        250.0,
    )
    assert (batch["shiv_pct"], batch["dust_pct"]) == (55.0, 15.0)
    listed = client.get(HEAPS, params={"site_id": sites["BWP-G1"], "status": "open"}).json()
    assert [h["heap_id"] for h in listed] == ["BWP-G1-H02", "BWP-G1-H01"]
    config = {c["crop"]: c for c in client.get(f"{HEAPS}/config").json()}
    assert config["cotton"]["default_outturn_ratio_pct"] == 34.0
    assert config["hemp"]["default_dust_pct"] == 15.0


def test_assignment_rules(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    make_request: Callable[..., Json],
    schedule: Callable[..., Json],
) -> None:
    heap = open_heap("BWP-G1")
    good = delivered(8000)
    elsewhere = delivered(5000, site="BWP-G2")
    hemp = delivered(3000, site="UK-P1", crop="hemp")
    moving = schedule(make_request())
    assert [p["id"] for p in client.get(f"{HEAPS}/{heap['id']}").json()["pending_deliveries"]] == [
        good["id"]
    ]
    body = add(client, heap, good, elsewhere, hemp, moving)
    assert body["added"] == [good["id"]]
    codes = {s["delivery_no"]: s["code"] for s in body["skipped"]}
    assert codes == {
        elsewhere["delivery_no"]: "delivery_wrong_site",
        hemp["delivery_no"]: "delivery_wrong_site",
        moving["delivery_no"]: "delivery_not_delivered",
    }
    assert body["heap"]["totals"]["input_kg"] == "8000.00"
    other = open_heap("BWP-G1")
    again = add(client, other, good)
    assert again["skipped"][0]["code"] == "delivery_already_assigned"
    assert client.get(f"{DL}/{good['id']}").json()["heap_id"] == "BWP-G1-H01"


def test_the_documented_example_end_to_end(
    client: TestClient, open_heap: Callable[..., Json], delivered: Callable[..., Json]
) -> None:
    heap = open_heap()
    detail = add(client, heap, delivered(8000), delivered(5000), delivered(4000))["heap"]
    t = detail["totals"]
    assert (t["input_kg"], t["input_maunds"], t["expected_output_kg"], t["max_bales"]) == (
        "17000.00",
        "425.00",
        "5780.00",
        34,
    )
    shares = detail["contributions"]
    assert [c["pct"] for c in shares] == ["47.06", "29.41", "23.53"]
    assert sum(Decimal(c["pct"]) for c in shares) == Decimal("100.00")
    made = client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 34}).json()
    assert made["totals"]["bales_made"] == 34
    assert [b["bale_serial"] for b in made["bales"]][:2] == ["BWP-G1-H01-001", "BWP-G1-H01-002"]
    assert made["bales"][-1]["bale_serial"] == "BWP-G1-H01-034"
    over = client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 1})
    assert (over.status_code, over.json()["error"]["code"]) == (409, "heap_bale_limit")
    assert made["permissions"]["can_close"] is True
    closed = client.post(f"{HEAPS}/{heap['id']}/close", json={}).json()
    assert closed["status"] == "closed"
    contributors = client.get(f"{HEAPS}/{heap['id']}/contributors").json()
    assert len(contributors) == 3


def test_values_freeze_with_the_first_bale(
    client: TestClient, open_heap: Callable[..., Json], delivered: Callable[..., Json]
) -> None:
    heap = open_heap()
    add(client, heap, delivered(5000))
    edited = client.put(
        f"{HEAPS}/{heap['id']}", json={"outturn_ratio_pct": 35, "bale_unit_kg": 175}
    ).json()
    assert (edited["outturn_ratio_pct"], edited["totals"]["max_bales"]) == (35.0, 10)
    assert client.put(f"{HEAPS}/{heap['id']}", json={"outturn_ratio_pct": 0}).status_code == 422
    client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 1})
    frozen = client.put(f"{HEAPS}/{heap['id']}", json={"outturn_ratio_pct": 30})
    assert (frozen.status_code, frozen.json()["error"]["code"]) == (409, "heap_values_frozen")
    assert (
        client.put(f"{HEAPS}/{heap['id']}", json={"note": "Cleaned lot"}).json()["note"]
        == "Cleaned lot"
    )


def test_bales_never_exceed_the_maximum_under_concurrency(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    officer_ids: dict[str, str],
) -> None:
    heap = open_heap()
    add(client, heap, delivered(5000))  # 1,700 kg expected: 10 bales of 170 kg
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
    threads, made, refused, errors = 8, [], [], []
    lock, start = threading.Lock(), threading.Barrier(threads)

    def worker() -> None:
        session = db.session_factory()
        try:
            start.wait(timeout=30)
            bales = HeapService(session).create_bales(heap["id"], officer, 3)
            with lock:
                made.extend(b.bale_serial for b in bales)
        except Exception as exc:  # noqa: BLE001
            with lock:
                (refused if getattr(exc, "code", "") == "heap_bale_limit" else errors).append(exc)
        finally:
            session.close()

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    assert errors == []
    assert len(made) == 9  # three calls of 3 fit in 10; the rest are refused
    assert len(set(made)) == 9
    assert len(refused) == threads - 3
    final = client.get(f"{HEAPS}/{heap['id']}").json()["totals"]
    assert (final["bales_made"], final["max_bales"]) == (9, 10)


def test_close_rules(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    empty = open_heap()
    r = client.post(f"{HEAPS}/{empty['id']}/close", json={})
    assert r.json()["error"]["code"] == "heap_empty"

    heap = open_heap()
    add(client, heap, delivered(5000))
    no_reason = client.post(f"{HEAPS}/{heap['id']}/close", json={"with_remainder": True})
    assert no_reason.json()["error"]["code"] == "heap_reason_required"  # zero bales
    client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 4})
    remainder = client.post(f"{HEAPS}/{heap['id']}/close", json={})
    assert (remainder.status_code, remainder.json()["error"]["code"]) == (409, "heap_has_remainder")
    officer = client.post(
        f"{HEAPS}/{heap['id']}/close", json={"with_remainder": True, "reason": "Gin broke down"}
    )
    assert officer.status_code == 403  # only administrators close with a remainder
    admin = as_officer("ADMIN-01")
    detail = client.get(f"{HEAPS}/{heap['id']}", headers=admin).json()
    assert detail["permissions"]["can_close_with_remainder"] is True
    assert (
        client.post(
            f"{HEAPS}/{heap['id']}/close", json={"with_remainder": True}, headers=admin
        ).status_code
        == 422
    )
    closed = client.post(
        f"{HEAPS}/{heap['id']}/close",
        headers=admin,
        json={"with_remainder": True, "reason": "Gin broke down"},
    ).json()
    assert (closed["status"], closed["close_reason"]) == ("closed", "Gin broke down")
    db = client.app.state.db  # type: ignore[attr-defined]
    from sqlalchemy import select

    from shared.models.audit_log import AuditLog

    with db.session_scope() as s:
        entry = s.execute(
            select(AuditLog).where(AuditLog.entity_id == heap["id"], AuditLog.action == "close")
        ).scalar_one()
        assert entry.diff["with_remainder"] is True
        assert entry.diff["remaining_output_kg"] == "1020.00"


def test_closed_heaps_are_locked(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    heap = open_heap()
    member = delivered(1000)  # 340 kg: 2 bales
    add(client, heap, member)
    client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 2})
    assert client.post(f"{HEAPS}/{heap['id']}/close", json={}).status_code == 200
    admin = as_officer("ADMIN-01")
    attempts = [
        client.post(
            f"{HEAPS}/{heap['id']}/deliveries", json={"delivery_ids": [delivered(500)["id"]]}
        ),
        client.delete(f"{HEAPS}/{heap['id']}/deliveries/{member['id']}", params={"reason": "x"}),
        client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 1}),
        client.put(f"{HEAPS}/{heap['id']}", json={"note": "x"}),
        client.post("/api/v1/heaps/bales/BWP-G1-H01-001/void", json={"reason": "x"}, headers=admin),
        client.post(f"{HEAPS}/{heap['id']}/close", json={}),
    ]
    for r in attempts:
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == "heap_closed"
    # An administrator correction of a delivery in a closed heap is refused by the guard.
    fix = client.post(
        f"{DL}/{member['id']}/correct",
        headers=admin,
        json={"reason": "Ticket misread", "weighbridge_weight_kg": 990},
    )
    assert (fix.status_code, fix.json()["error"]["code"]) == (409, "heap_closed")


def test_removing_and_voiding(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    heap = open_heap()
    a, b = delivered(2000), delivered(3000)
    add(client, heap, a, b)
    url = f"{HEAPS}/{heap['id']}/deliveries/{a['id']}"
    assert client.delete(url, params={"reason": " "}).status_code == 422
    after = client.delete(url, params={"reason": "Belongs to the next heap"}).json()
    assert [d["delivery_id"] for d in after["deliveries"]] == [b["id"]]
    assert client.get(f"{DL}/{a['id']}").json()["heap_id"] is None
    client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 2})
    blocked = client.delete(f"{HEAPS}/{heap['id']}/deliveries/{b['id']}", params={"reason": "x"})
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "heap_has_bales")
    serial = "BWP-G1-H01-002"
    officer_void = client.post(f"{HEAPS}/bales/{serial}/void", json={"reason": "Wet"})
    assert officer_void.status_code == 403
    admin = as_officer("ADMIN-01")
    assert (
        client.post(f"{HEAPS}/bales/{serial}/void", json={"reason": ""}, headers=admin).status_code
        == 422
    )
    voided = client.post(
        f"{HEAPS}/bales/{serial}/void", json={"reason": "Wet bale"}, headers=admin
    ).json()
    assert (voided["status"], voided["void_reason"]) == ("voided", "Wet bale")
    more = client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 1}).json()
    serials = [x["bale_serial"] for x in more["bales"]]
    assert serials == ["BWP-G1-H01-001", "BWP-G1-H01-002", "BWP-G1-H01-003"]  # never reused
    assert more["totals"]["bales_made"] == 2


def test_correction_in_an_open_heap_recomputes(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    heap = open_heap()
    member = delivered(1000)
    add(client, heap, member)
    fixed = client.post(
        f"{DL}/{member['id']}/correct",
        headers=as_officer("ADMIN-01"),
        json={"reason": "Second weighing", "weighbridge_weight_kg": 2000},
    )
    assert fixed.status_code == 200, fixed.text
    assert client.get(f"{HEAPS}/{heap['id']}").json()["totals"]["input_kg"] == "2000.00"


def test_events(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    member = delivered(1000)
    with bus.capture() as seen:
        heap = open_heap()
        add(client, heap, member)
        client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 2})
        client.post(
            f"{HEAPS}/bales/BWP-G1-H01-001/void",
            json={"reason": "Torn"},
            headers=as_officer("ADMIN-01"),
        )
        client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 1})
        client.post(f"{HEAPS}/{heap['id']}/close", json={})
    names = [e.name for e in seen if e.name.startswith(("heap.", "bale."))]
    assert names == [
        "heap.opened",
        "bale.created",
        "bale.created",
        "bale.voided",
        "bale.created",
        "heap.closed",
    ]
    created = [e.payload for e in seen if e.name == "bale.created"]
    assert [p["bale_serial"] for p in created] == [
        "BWP-G1-H01-001",
        "BWP-G1-H01-002",
        "BWP-G1-H01-003",
    ]
    assert all(p["heap_id"] == "BWP-G1-H01" for p in created)


def test_public_api_and_lineage(
    client: TestClient,
    open_heap: Callable[..., Json],
    delivered: Callable[..., Json],
    sites: dict[str, str],
) -> None:
    heap = open_heap()
    a, b = delivered(3000), delivered(1000)
    delivered(500)  # pending at the same site
    add(client, heap, a, b)
    client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": 2})
    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session_scope() as s:
        assert api.get_heap(s, "BWP-G1-H01").kind == "heap"  # type: ignore[union-attr]
        assert [h.heap_id for h in api.list_open_heaps(s, sites["BWP-G1"])] == ["BWP-G1-H01"]
        totals = api.get_heap_totals(s, "BWP-G1-H01")
        assert totals is not None
        assert (totals.input_kg, totals.max_bales, totals.bales_made) == (Decimal("4000.00"), 8, 2)
        assert [x.bale_serial for x in api.list_bales(s, "BWP-G1-H01")] == [
            "BWP-G1-H01-001",
            "BWP-G1-H01-002",
        ]
        bale = api.get_bale(s, "BWP-G1-H01-002")
        assert bale is not None
        assert bale.heap_id == "BWP-G1-H01"
        lineage = api.get_heap_lineage(s, "BWP-G1-H01")
        assert lineage is not None
        assert [f.pct for f in lineage.farmers] == [Decimal("75.00"), Decimal("25.00")]
        first = lineage.farmers[0]
        assert first.fields[0].delivery_nos == (a["delivery_no"],)
        assert first.fields[0].fieldbook_id is not None
        assert first.fields[0].sowing_date is not None
        inv = api.get_site_inventory_summary(s, sites["BWP-G1"])
        assert (inv.open_heaps, inv.pending_deliveries, inv.pending_kg, inv.active_bales) == (
            1,
            1,
            Decimal("500.00"),
            2,
        )


@pytest.mark.parametrize("crop", ["cotton", "hemp"])
def test_csv(
    client: TestClient, open_heap: Callable[..., Json], delivered: Callable[..., Json], crop: str
) -> None:
    site = "BWP-G1" if crop == "cotton" else "UK-P1"
    heap = open_heap(site, officer="PK-MUL-01" if crop == "cotton" else "GB-EOE-01")
    add(client, heap, delivered(2000, site=site, crop=crop))
    r = client.get(f"{HEAPS}/{heap['id']}/export.csv")
    text = r.content.decode("utf-8-sig")
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert text.splitlines()[0].startswith("Heap," if crop == "cotton" else "Batch,")
