"""Deliveries API: inbox, bulk scheduling, the status machine, receiving, cancelling,
administrator corrections, scoping, the slip, statistics and the CSV."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from module_5.tests.conftest import DL, RADAR, TOMORROW, YEAR, transport

Farm = dict[str, Any]


def radar_row(client: TestClient, farm: Farm) -> dict[str, Any]:
    page = client.get(
        f"{RADAR}/fields", params={"crop": farm["crop"], "page_size": 100}, headers=farm["headers"]
    ).json()
    return next(r for r in page["items"] if r["field_id"] == farm["field"]["id"])


class TestInboxAndSchedule:
    def test_inbox_lists_waiting_requests(
        self, client: TestClient, make_request: Callable[..., Farm]
    ) -> None:
        farm = make_request()
        rows = client.get(f"{DL}/inbox", headers=farm["headers"]).json()
        assert [r["request_id"] for r in rows] == [farm["request"]["id"]]
        row = rows[0]
        assert row["farmer_name"] == farm["farmer"]["name"]
        assert row["location"] == "Basti Malook, Multan City, Multan"
        assert row["estimated_quantity_kg"] > 0
        assert row["can_schedule"] is True

    def test_scheduling_creates_a_delivery_and_radar_follows(
        self, client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        assert dl["delivery_no"] == "DL-0001"
        assert dl["status"] == "scheduled"
        assert dl["vehicle_no"] == "MNA-1234"
        assert dl["driver_phone"] == "+923017654321"
        assert dl["site"]["code"] == "BWP-G1"
        assert dl["estimated_quantity_kg"] == farm["request"]["estimated_quantity_kg"]
        assert radar_row(client, farm)["pickup_state"] == "scheduled"
        assert client.get(f"{DL}/inbox", headers=farm["headers"]).json() == []
        req = client.get(f"{RADAR}/pickup-requests", headers=farm["headers"]).json()["items"][0]
        assert (req["status"], req["delivery_id"]) == ("scheduled", dl["id"])

    def test_bulk_scheduling_partial_success(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        sites: dict[str, str],
        schedule: Callable[..., Any],
    ) -> None:
        a, b = make_request(), make_request()
        already = make_request()
        schedule(already)
        theirs = make_request(officer="PK-BWP-01")
        body = {
            "request_ids": [
                a["request"]["id"],
                b["request"]["id"],
                already["request"]["id"],
                theirs["request"]["id"],
                "nope",
            ],
            **transport(sites["BWP-G2"]),
        }
        r = client.post(f"{DL}/schedule", json=body, headers=a["headers"])
        assert r.status_code == 201
        res = r.json()
        assert [c["field_code"] for c in res["created"]] == [
            a["field"]["field_id"],
            b["field"]["field_id"],
        ]
        assert all(c["vehicle_no"] == "MNA-1234" for c in res["created"])
        assert {s["code"] for s in res["skipped"]} == {
            "pickup_not_waiting",
            "delivery_forbidden",
            "pickup_not_found",
        }

    def test_site_crop_must_match(
        self, client: TestClient, make_request: Callable[..., Farm], sites: dict[str, str]
    ) -> None:
        farm = make_request()
        r = client.post(
            f"{DL}/schedule",
            headers=farm["headers"],
            json={"request_ids": [farm["request"]["id"]], **transport(sites["UK-P1"], "hemp")},
        )
        assert r.json()["skipped"][0]["code"] == "site_crop_mismatch"
        assert r.json()["created"] == []

    @pytest.mark.parametrize(
        ("over", "field"),
        [
            ({"scheduled_date": (date.today() - timedelta(days=1)).isoformat()}, None),
            ({"driver_phone": "12345"}, "driver_phone"),
            ({"driver_phone": "07700 900123"}, "driver_phone"),  # a UK number for a Pakistani site
            ({"vehicle_no": "!"}, "vehicle_no"),
            ({"driver_name": " "}, "driver_name"),
        ],
    )
    def test_schedule_validation(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        sites: dict[str, str],
        over: dict[str, Any],
        field: str | None,
    ) -> None:
        farm = make_request()
        r = client.post(
            f"{DL}/schedule",
            headers=farm["headers"],
            json={"request_ids": [farm["request"]["id"]], **transport(sites["BWP-G1"], **over)},
        )
        assert r.status_code == 422
        if field:
            assert r.json()["error"]["details"]["fields"][0]["field"] == field

    def test_hemp_uses_uk_phones(
        self, make_request: Callable[..., Farm], schedule: Callable[..., Any]
    ) -> None:
        dl = schedule(make_request("hemp"))
        assert (dl["driver_phone"], dl["vehicle_no"], dl["site"]["type"]) == (
            "+447700900456",
            "AB12 CDE",
            "processor",
        )


class TestStateMachine:
    def test_the_happy_path_and_its_history(
        self, client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        h = farm["headers"]
        sent = client.post(
            f"{DL}/{dl['id']}/dispatch", json={"field_weight_kg": 3000}, headers=h
        ).json()
        assert sent["delivery"]["status"] == "in_transit"
        assert sent["delivery"]["dispatched_at"]
        got = client.post(
            f"{DL}/{dl['id']}/receive",
            json={"weighbridge_weight_kg": 3060, "moisture_pct": 9},
            headers=h,
        ).json()
        d = got["delivery"]
        assert d["status"] == "delivered"
        assert (d["variance_kg"], d["variance_pct"], d["variance_level"]) == (60, 2.0, "ok")
        assert d["weighbridge_maunds"] == 76.5
        assert d["heap_id"] is None
        assert [(x["from_status"], x["to_status"]) for x in d["history"]] == [
            (None, "scheduled"),
            ("scheduled", "in_transit"),
            ("in_transit", "delivered"),
        ]
        assert d["thresholds"] == {
            "variance_warn_pct": 3.0,
            "variance_flag_pct": 5.0,
            "moisture_warn_pct": 12.0,
        }

    @pytest.mark.parametrize(
        ("path", "body", "state"),
        [
            ("receive", {"weighbridge_weight_kg": 100, "moisture_pct": 9}, "scheduled"),
            ("dispatch", {}, "in_transit"),
            ("dispatch", {}, "delivered"),
            ("receive", {"weighbridge_weight_kg": 100, "moisture_pct": 9}, "delivered"),
            ("cancel", {"reason": "x"}, "delivered"),
            ("dispatch", {}, "cancelled"),
            ("receive", {"weighbridge_weight_kg": 100, "moisture_pct": 9}, "cancelled"),
            ("cancel", {"reason": "x"}, "cancelled"),
        ],
    )
    def test_invalid_transitions_are_refused(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        schedule: Callable[..., Any],
        path: str,
        body: dict[str, Any],
        state: str,
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        h = farm["headers"]
        if state in ("in_transit", "delivered"):
            client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=h)
        if state == "delivered":
            client.post(
                f"{DL}/{dl['id']}/receive",
                headers=h,
                json={"weighbridge_weight_kg": 100, "moisture_pct": 9, "note": "Part load"},
            )
        if state == "cancelled":
            client.post(f"{DL}/{dl['id']}/cancel", json={"reason": "Lorry broke down"}, headers=h)
        r = client.post(f"{DL}/{dl['id']}/{path}", json=body, headers=h)
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == "invalid_transition"

    @pytest.mark.parametrize("state", ["scheduled", "in_transit"])
    def test_cancel_with_reason_releases_the_request(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        schedule: Callable[..., Any],
        state: str,
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        h = farm["headers"]
        if state == "in_transit":
            client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=h)
        assert (
            client.post(f"{DL}/{dl['id']}/cancel", json={"reason": " "}, headers=h).status_code
            == 422
        )
        r = client.post(f"{DL}/{dl['id']}/cancel", json={"reason": "Road closed"}, headers=h).json()
        assert (r["status"], r["cancel_reason"]) == ("cancelled", "Road closed")
        req = client.get(f"{RADAR}/pickup-requests", headers=h).json()["items"][0]
        assert req["status"] == "cancelled"
        assert "DL-0001" in req["cancel_reason"]
        row = radar_row(client, farm)
        assert (row["pickup_state"], row["can_request"]) == ("not_requested", True)

    def test_edit_only_while_scheduled(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        schedule: Callable[..., Any],
        sites: dict[str, str],
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        h = farm["headers"]
        ok = client.put(
            f"{DL}/{dl['id']}",
            json={"vehicle_no": "lhr 999", "site_id": sites["MUX-G1"]},
            headers=h,
        )
        assert (ok.json()["vehicle_no"], ok.json()["site"]["code"]) == ("LHR 999", "MUX-G1")
        bad_site = client.put(f"{DL}/{dl['id']}", json={"site_id": sites["UK-P2"]}, headers=h)
        assert bad_site.json()["error"]["code"] == "site_crop_mismatch"
        client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=h)
        locked = client.put(f"{DL}/{dl['id']}", json={"vehicle_no": "X1"}, headers=h)
        assert (locked.status_code, locked.json()["error"]["code"]) == (409, "delivery_locked")


class TestReceive:
    def test_weight_and_moisture_are_validated(
        self, client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        h = farm["headers"]
        client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=h)
        for body in (
            {"weighbridge_weight_kg": 0, "moisture_pct": 9},
            {"weighbridge_weight_kg": 100, "moisture_pct": 101},
            {"weighbridge_weight_kg": 100, "moisture_pct": -1},
        ):
            assert client.post(f"{DL}/{dl['id']}/receive", json=body, headers=h).status_code == 422

    def test_flag_needs_a_note_and_moisture_warns(
        self, client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        h = farm["headers"]
        client.post(f"{DL}/{dl['id']}/dispatch", json={"field_weight_kg": 1000}, headers=h)
        no_note = client.post(
            f"{DL}/{dl['id']}/receive",
            json={"weighbridge_weight_kg": 1060, "moisture_pct": 13},
            headers=h,
        )
        assert no_note.json()["error"]["code"] == "delivery_flag_note_required"
        ok = client.post(
            f"{DL}/{dl['id']}/receive",
            headers=h,
            json={"weighbridge_weight_kg": 1060, "moisture_pct": 13, "note": "Wet load after rain"},
        ).json()
        assert ok["delivery"]["variance_level"] == "flag"
        assert ok["warnings"] == ["Moisture 13% is above the 12% limit for this crop."]
        assert "Wet load after rain" in ok["delivery"]["note"]

    def test_warn_level_reports_a_warning(
        self, client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
    ) -> None:
        farm = make_request("hemp")
        dl = schedule(farm)
        h = farm["headers"]
        client.post(f"{DL}/{dl['id']}/dispatch", json={"field_weight_kg": 1000}, headers=h)
        ok = client.post(
            f"{DL}/{dl['id']}/receive",
            json={"weighbridge_weight_kg": 960, "moisture_pct": 15},
            headers=h,
        ).json()
        assert ok["delivery"]["variance_level"] == "warn"
        assert ok["warnings"] == ["The weight differs by -4% from the field weight."]
        assert ok["delivery"]["weighbridge_maunds"] is None  # maunds are for cotton only

    def test_receiving_closes_the_request_and_frees_the_field(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        deliver: Callable[..., Any],
    ) -> None:
        farm = make_request()
        deliver(farm, weighbridge=1900)
        h = farm["headers"]
        req = client.get(f"{RADAR}/pickup-requests", headers=h).json()["items"][0]
        assert req["status"] == "fulfilled"
        assert req["delivery_id"]
        row = radar_row(client, farm)
        assert (row["pickup_state"], row["can_request"]) == ("delivered", True)


class TestScopingAndCorrection:
    def test_officers_act_only_for_their_farmers(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        schedule: Callable[..., Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        other = as_officer("PK-BWP-01")
        assert client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=other).status_code == 403
        assert client.get(f"{DL}", headers=other).json()["total"] == 0
        seen = client.get(f"{DL}", params={"scope": "all"}, headers=other).json()
        assert seen["total"] == 1
        assert seen["items"][0]["can_act"] is False
        assert client.get(f"{DL}/{dl['id']}", headers=other).json()["can_act"] is False
        admin = as_officer("ADMIN-01")
        assert client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=admin).status_code == 200

    def test_delivered_records_are_immutable_except_admin_correction(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        deliver: Callable[..., Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_request()
        d = deliver(farm, weighbridge=2000)
        h = farm["headers"]
        assert (
            client.put(f"{DL}/{d['id']}", json={"vehicle_no": "X12"}, headers=h).status_code == 409
        )
        officer_fix = client.post(
            f"{DL}/{d['id']}/correct",
            json={"reason": "typo", "weighbridge_weight_kg": 1},
            headers=h,
        )
        assert officer_fix.status_code == 403
        admin = as_officer("ADMIN-01")
        no_reason = client.post(
            f"{DL}/{d['id']}/correct", json={"reason": " ", "moisture_pct": 10}, headers=admin
        )
        assert no_reason.status_code == 422
        fixed = client.post(
            f"{DL}/{d['id']}/correct",
            headers=admin,
            json={"reason": "Weighbridge ticket misread", "weighbridge_weight_kg": 2100},
        ).json()
        assert fixed["delivery"]["weighbridge_weight_kg"] == 2100
        assert fixed["delivery"]["status"] == "delivered"
        assert fixed["delivery"]["history"][-1]["note"] == "Correction: Weighbridge ticket misread"
        db = client.app.state.db  # type: ignore[attr-defined]
        from sqlalchemy import select

        from shared.models.audit_log import AuditLog

        with db.session_scope() as s:
            entry = s.execute(
                select(AuditLog).where(AuditLog.entity_id == d["id"], AuditLog.action == "correct")
            ).scalar_one()
            assert entry.diff["reason"] == "Weighbridge ticket misread"
            assert entry.diff["weighbridge_weight_kg"] == {"from": 2000.0, "to": 2100.0}

    def test_correcting_a_record_that_is_not_delivered_is_refused(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        schedule: Callable[..., Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        dl = schedule(make_request())
        r = client.post(
            f"{DL}/{dl['id']}/correct",
            json={"reason": "x", "moisture_pct": 5},
            headers=as_officer("ADMIN-01"),
        )
        assert r.status_code == 409


class TestOutputs:
    def test_slip_pdf(
        self, client: TestClient, make_request: Callable[..., Farm], schedule: Callable[..., Any]
    ) -> None:
        farm = make_request()
        dl = schedule(farm)
        r = client.get(f"{DL}/{dl['id']}/slip.pdf", headers=farm["headers"])
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 2000
        assert "slip_DL-0001.pdf" in r.headers["content-disposition"]

    def test_stats_and_list_filters(
        self,
        client: TestClient,
        make_request: Callable[..., Farm],
        schedule: Callable[..., Any],
        deliver: Callable[..., Any],
    ) -> None:
        waiting = make_request()
        schedule(make_request())
        d = make_request()
        deliver(d, weighbridge=4000)
        h = waiting["headers"]
        s = client.get(f"{DL}/stats", headers=h).json()
        assert (
            s["requests_waiting"],
            s["scheduled"],
            s["in_transit"],
            s["delivered_this_week"],
        ) == (1, 1, 0, 1)
        assert (s["delivered_this_week_kg"], s["delivered_this_week_maunds"]) == (4000, 100)
        page = client.get(f"{DL}", params={"status": "delivered"}, headers=h).json()
        assert page["total"] == 1
        assert page["status_counts"] == {
            "scheduled": 1,
            "in_transit": 0,
            "delivered": 1,
            "cancelled": 0,
        }
        assert client.get(f"{DL}", params={"q": "DL-0002"}, headers=h).json()["total"] == 1
        assert client.get(f"{DL}", params={"q": "mna-1234"}, headers=h).json()["total"] == 2
        assert (
            client.get(f"{DL}", params={"q": str(d["farmer"]["sawie_id"])}, headers=h).json()[
                "total"
            ]
            == 1
        )
        assert client.get(f"{DL}", params={"district": "Multan"}, headers=h).json()["total"] == 2
        assert client.get(f"{DL}", params={"crop": "hemp"}, headers=h).json()["total"] == 0
        tomorrow = client.get(
            f"{DL}", params={"date_from": TOMORROW, "date_to": TOMORROW}, headers=h
        ).json()
        assert tomorrow["total"] == 2

    def test_csv(
        self, client: TestClient, make_request: Callable[..., Farm], deliver: Callable[..., Any]
    ) -> None:
        farm = make_request()
        deliver(farm, weighbridge=4000)
        r = client.get(f"{DL}/export.csv", headers=farm["headers"])
        assert r.content.startswith(b"\xef\xbb\xbf")
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        assert rows[0][0] == "Delivery"
        assert rows[1][0] == "DL-0001"
        assert rows[1][rows[0].index("Weighbridge (maunds)")] == "100.0"

    def test_sites_endpoint(self, client: TestClient) -> None:
        cotton = client.get("/api/v1/sites", params={"crop": "cotton"}).json()
        assert [s["code"] for s in cotton] == ["BWP-G1", "BWP-G2", "BWP-G3", "MUX-G1"]
        assert all(s["is_dummy"] and s["type"] == "ginner" for s in cotton)
        hemp = client.get("/api/v1/sites", params={"crop": "hemp"}).json()
        assert [(s["code"], s["type"]) for s in hemp] == [
            ("UK-P1", "processor"),
            ("UK-P2", "processor"),
        ]


def test_year_constant_is_this_year() -> None:
    assert date.today().year == YEAR
