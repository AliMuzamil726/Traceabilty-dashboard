"""QR Tracing end to end on a seeded lot: three farmers contributing 50, 30 and 20 percent."""

from __future__ import annotations

import base64
import json
import re
import zlib
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.events import bus
from core.network import reachable_base_url
from module_7 import public_api as api
from module_7.models import QrScanLog, QrToken
from module_7.services import cache, images, scans
from module_7.tests.conftest import HEAPS, QR

Json = dict[str, Any]


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    cache.invalidate()
    scans.public_limiter.reset()
    yield
    scans.public_limiter.reset()


@pytest.fixture
def lot(
    client: TestClient,
    make_request: Callable[..., Json],
    deliver: Callable[..., Json],
    sites: dict[str, str],
) -> Callable[..., Json]:
    """Three farmers, 5,000, 3,000 and 2,000 kg, in one heap at BWP-G1, with bales."""

    def _lot(*, submit_all: bool = True, close: bool = True, bales: int = 20) -> Json:
        farms = [make_request(submit=submit_all or i > 0) for i in range(3)]
        delivered = [
            deliver(f, site="BWP-G1", weighbridge=kg)
            for f, kg in zip(farms, (5000, 3000, 2000), strict=True)
        ]
        heap = client.post(HEAPS, json={"site_id": sites["BWP-G1"]}).json()["heap"]
        client.post(
            f"{HEAPS}/{heap['id']}/deliveries", json={"delivery_ids": [d["id"] for d in delivered]}
        )
        detail = client.post(f"{HEAPS}/{heap['id']}/bales", json={"count": bales}).json()
        if close:
            detail = client.post(f"{HEAPS}/{heap['id']}/close", json={"reason": "Test lot"}).json()
        return {"farms": farms, "deliveries": delivered, "heap": detail}

    return _lot


def pdf_text(content: bytes) -> bytes:
    """The page streams of a reportlab PDF (ASCII85 then Flate), decoded."""
    out = []
    for raw in re.findall(rb"stream\r?\n(.*?)endstream", content, re.S):
        data = raw.strip()
        try:
            if data.endswith(b"~>"):
                data = base64.a85decode(data[:-2])
            out.append(zlib.decompress(data))
        except (zlib.error, ValueError):
            out.append(raw)
    return b"\n".join(out)


def labels_in(content: bytes) -> int:
    return pdf_text(content).count(b"(Scan to trace) Tj")


def bale_rows(client: TestClient, heap_id: str) -> list[Json]:
    return client.get(f"{QR}/bales", params={"heap_id": heap_id}).json()


class TestTokensFromEvents:
    def test_every_heap_and_bale_gets_one_token(
        self, client: TestClient, lot: Callable[..., Json]
    ) -> None:
        heap = lot()["heap"]
        overview = client.get(f"{QR}/lots/{heap['heap_id']}/overview").json()
        assert len(overview["token"]) == 12
        rows = bale_rows(client, heap["heap_id"])
        assert len(rows) == 20
        assert all(r["token_status"] == "active" and len(r["token"]) == 12 for r in rows)
        assert len({r["token"] for r in rows} | {overview["token"]}) == 21
        assert all(r["bale_serial"] not in r["token"] for r in rows)

    def test_overview_names_the_farmers_in_the_lot(
        self, client: TestClient, lot: Callable[..., Json]
    ) -> None:
        data = lot()
        overview = client.get(f"{QR}/lots/{data['heap']['heap_id']}/overview").json()
        names = [f["farmer_name"] for f in overview["farmers"]]
        assert len(names) == 3
        assert all(names)
        assert sum(f["kg"] for f in overview["farmers"]) == pytest.approx(10_000.0)

    def test_creation_is_idempotent(self, client: TestClient, lot: Callable[..., Json]) -> None:
        heap = lot(close=False, bales=1)["heap"]
        db = client.app.state.db  # type: ignore[attr-defined]
        serial = f"{heap['heap_id']}-001"
        with db.session_scope() as s:
            for _ in range(3):
                bus.publish(
                    "bale.created", {"bale_serial": serial, "heap_id": heap["heap_id"]}, session=s
                )
                bus.publish("heap.opened", {"heap_id": heap["heap_id"]}, session=s)
        with db.session_scope() as s:
            rows = (
                s.execute(select(QrToken).where(QrToken.heap_id == heap["heap_id"])).scalars().all()
            )
            assert sorted(r.token_type for r in rows) == ["bale", "heap"]

    def test_voiding_a_bale_revokes_its_token(
        self,
        client: TestClient,
        lot: Callable[..., Json],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        heap = lot(close=False, bales=2)["heap"]
        serial = f"{heap['heap_id']}-002"
        token = next(
            r["token"] for r in bale_rows(client, heap["heap_id"]) if r["bale_serial"] == serial
        )
        assert client.get(f"{QR}/public/{token}").status_code == 200
        client.post(
            f"{HEAPS}/bales/{serial}/void", json={"reason": "Torn"}, headers=as_officer("ADMIN-01")
        )
        r = client.get(f"{QR}/public/{token}")
        assert (r.status_code, r.json()["error"]["message"]) == (404, "This code is not valid")
        row = next(r for r in bale_rows(client, heap["heap_id"]) if r["bale_serial"] == serial)
        assert (row["bale_status"], row["token_status"]) == ("voided", "revoked")


class TestPublicTrace:
    def test_payload_contents(self, client: TestClient, lot: Callable[..., Json]) -> None:
        data = lot()
        heap = data["heap"]
        row = bale_rows(client, heap["heap_id"])[0]
        body = client.get(f"{QR}/public/{row['token']}").json()
        assert body["product"] == "Cotton lint bale"
        assert (body["bale_serial"], body["weight_kg"], body["lot_id"]) == (
            row["bale_serial"],
            170.0,
            heap["heap_id"],
        )
        assert body["site"] == {
            "type": "Ginner",
            "name": "Bahawalpur Ginner 1 (dummy)",
            "region": "Bahawalpur",
        }
        assert (body["programme"], body["country"]) == ("Pakistan cotton", "Pakistan")
        assert (body["farms"], body["fields"]) == (3, 3)
        assert (body["region_level"], body["regions"]) == ("District", ["Multan"])
        assert body["harvest_window"]["from"]
        assert body["harvest_window"]["to"]
        assert [t["label"] for t in body["timeline"]] == [
            "Farmers registered",
            "Fields mapped",
            "Fieldbooks submitted",
            "Harvest",
            "Delivery",
            "Heap processing",
            "Bale produced",
        ]
        assert {t["key"]: t["count"] for t in body["timeline"]}["fieldbooks"] == 3
        assert all(c["passed"] for c in body["checks"]), body["checks"]

    def test_heap_token_page(self, client: TestClient, lot: Callable[..., Json]) -> None:
        heap = lot()["heap"]
        token = client.get(f"{QR}/lots/{heap['heap_id']}/overview").json()["token"]
        body = client.get(f"{QR}/public/{token}").json()
        assert (body["product"], body["bale_serial"]) == ("Cotton lint heap", None)
        assert {t["key"]: t["count"] for t in body["timeline"]}["bale"] == 20

    def test_privacy(self, client: TestClient, lot: Callable[..., Json]) -> None:
        data = lot()
        heap = data["heap"]
        rows = bale_rows(client, heap["heap_id"])
        body = client.get(f"{QR}/public/{rows[0]['token']}").json()
        text = json.dumps(body)
        banned_values: list[str] = [
            "Basti Malook",
            "Ghulam",
            "ghulam",
            "Muhammad Imran Khan",
            "+92",
            "0300",
            "35202",
            "MNA-1234",
            "Akram",
        ]
        for farm in data["farms"]:
            f = farm["farmer"]
            banned_values += [
                f["name"],
                f["id"],
                farm["field"]["id"],
                farm["field"]["field_id"],
                str(farm["field"]["pin_lat"]),
            ]
        banned_values += [d["id"] for d in data["deliveries"]] + [
            d["delivery_no"] for d in data["deliveries"]
        ]
        banned_values += [heap["id"]] + [
            r["bale_serial"] for r in rows[1:]
        ]  # never another bale's serial
        for value in banned_values:
            assert value not in text, value
        banned_keys = {
            "name_full",
            "farmer_name",
            "id_number",
            "phone",
            "village",
            "farm_name",
            "licence",
            "licence_no",
            "postcode",
            "geometry",
            "coordinates",
            "lat",
            "lng",
            "centroid",
            "pin_lat",
            "officer",
            "officer_name",
            "farmer_id",
            "field_id",
            "delivery_id",
            "vehicle_no",
            "id",
        }

        def keys(value: Any) -> set[str]:
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value)) if value else set()
            return set()

        assert not (keys(body) & banned_keys), keys(body) & banned_keys

    def test_unknown_and_revoked_codes_look_the_same(
        self,
        client: TestClient,
        lot: Callable[..., Json],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        heap = lot(close=False, bales=1)["heap"]
        token = bale_rows(client, heap["heap_id"])[0]["token"]
        client.post(
            f"{QR}/tokens/{token}/revoke",
            json={"reason": "Label damaged"},
            headers=as_officer("ADMIN-01"),
        )
        revoked = client.get(f"{QR}/public/{token}")
        unknown = client.get(f"{QR}/public/ABCDEFGHJKMN")
        nonsense = client.get(f"{QR}/public/not-a-token")
        assert revoked.status_code == unknown.status_code == nonsense.status_code == 404
        assert revoked.json() == unknown.json() == nonsense.json()

    def test_verification_is_honest(self, client: TestClient, lot: Callable[..., Json]) -> None:
        data = lot(submit_all=False, close=False)  # one fieldbook left as a draft, heap still open
        token = bale_rows(client, data["heap"]["heap_id"])[0]["token"]
        passed = {
            c["key"]: c["passed"] for c in client.get(f"{QR}/public/{token}").json()["checks"]
        }
        assert passed == {
            "fieldbooks_submitted": False,
            "deliveries_weighed": True,
            "heap_closed": False,
            "mass_balance": True,
        }

    def test_scans_are_logged_with_a_hash_only(
        self, client: TestClient, lot: Callable[..., Json]
    ) -> None:
        heap = lot()["heap"]
        token = bale_rows(client, heap["heap_id"])[0]["token"]
        r = client.get(
            f"{QR}/public/{token}", headers={"User-Agent": "Mozilla/5.0 (iPhone) Safari/604.1"}
        )
        assert r.headers["cache-control"] == "public, max-age=60"
        db = client.app.state.db  # type: ignore[attr-defined]
        with db.session_scope() as s:
            row = s.execute(select(QrScanLog)).scalars().one()
            assert row.channel == "public"
            assert row.user_agent_family == "Safari mobile"
            assert len(row.ip_hash or "") == 64
            assert "testclient" not in (row.ip_hash or "")
            assert row.ip_hash == scans.ip_hash("testclient", client.app.state.settings.qr_ip_salt)  # type: ignore[attr-defined]
        summary = client.get(f"{QR}/scans/summary", params={"heap_id": heap["heap_id"]}).json()
        assert (summary["total"], summary["public"]) == (1, 1)
        assert (
            next(b for b in bale_rows(client, heap["heap_id"]) if b["token"] == token)["scan_count"]
            == 1
        )

    def test_a_failing_scan_log_does_not_fail_the_page(
        self, client: TestClient, lot: Callable[..., Json], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heap = lot()["heap"]
        token = bale_rows(client, heap["heap_id"])[0]["token"]

        def boom(*_: Any, **__: Any) -> None:
            raise RuntimeError("disk full")

        monkeypatch.setattr(scans, "_write", boom)
        assert client.get(f"{QR}/public/{token}").status_code == 200

    def test_rate_limit(self, client: TestClient, lot: Callable[..., Json]) -> None:
        heap = lot(close=False, bales=1)["heap"]
        token = bale_rows(client, heap["heap_id"])[0]["token"]
        codes = [client.get(f"{QR}/public/{token}").status_code for _ in range(31)]
        assert codes[:30] == [200] * 30
        assert codes[30] == 429


class TestImagesAndLabels:
    def test_qr_encodes_the_configured_base_url(
        self, client: TestClient, lot: Callable[..., Json]
    ) -> None:
        heap = lot(close=False, bales=1)["heap"]
        row = bale_rows(client, heap["heap_id"])[0]
        # A localhost default is swapped for this computer's network address (D-123),
        # so a printed label can be opened by a phone without editing .env first.
        configured = client.app.state.settings.public_base_url  # type: ignore[attr-defined]
        base = reachable_base_url(configured)
        assert row["trace_url"] == f"{base}/trace/{row['token']}"
        png = client.get(f"{QR}/tokens/{row['token']}/image.png").content
        assert png == images.png(f"{base}/trace/{row['token']}")
        assert png.startswith(b"\x89PNG")
        svg = client.get(f"{QR}/tokens/{row['token']}/image.svg")
        assert svg.headers["content-type"].startswith("image/svg+xml")
        assert b"<svg" in svg.content
        lots = client.get(f"{QR}/lots", params={"crop": "cotton"}).json()
        assert lots["base_url"] == base
        assert lots["base_url_is_local"] is images.is_local(base)
        assert images.is_local("http://127.0.0.1:5173") is True
        assert images.is_local("http://192.168.1.20:5173") is False

    def test_label_sheet_counts_prints(self, client: TestClient, lot: Callable[..., Json]) -> None:
        heap = lot()["heap"]
        rows = bale_rows(client, heap["heap_id"])
        serials = [r["bale_serial"] for r in rows[:5]]
        pdf = client.post(f"{QR}/labels", json={"serials": serials})
        assert pdf.headers["content-type"] == "application/pdf"
        assert labels_in(pdf.content) == 5
        again = client.post(
            f"{QR}/labels", json={"serials": [r["bale_serial"] for r in rows]}
        )  # 20 labels
        assert labels_in(again.content) == 20
        counts = {
            r["bale_serial"]: r["label_print_count"] for r in bale_rows(client, heap["heap_id"])
        }
        assert [counts[s] for s in serials] == [2] * 5
        assert counts[rows[-1]["bale_serial"]] == 1
        png = client.get(f"{QR}/bales/{serials[0]}/label.png")
        assert png.content.startswith(b"\x89PNG")
        zipped = client.post(f"{QR}/images.zip", json={"serials": serials[:2]})
        assert zipped.content.startswith(b"PK")
        db = client.app.state.db  # type: ignore[attr-defined]
        from shared.models.audit_log import AuditLog

        with db.session_scope() as s:
            actions = [
                a.action
                for a in s.execute(select(AuditLog).where(AuditLog.entity == "qr_labels")).scalars()
            ]
            assert actions == ["print_labels", "print_labels", "print_label_png"]

    def test_a_full_page_holds_24_labels(
        self, client: TestClient, lot: Callable[..., Json]
    ) -> None:
        heap = lot(bales=20)["heap"]
        serials = [r["bale_serial"] for r in bale_rows(client, heap["heap_id"])]
        assert len(serials) == 20
        pdf = client.post(f"{QR}/labels", json={"serials": serials}).content
        assert labels_in(pdf) == 20
        assert len(re.findall(rb"/Type /Page[^s]", pdf)) == 1  # 20 labels fit one 3 x 8 sheet


class TestAdminActions:
    def test_revoke_and_regenerate_are_admin_only_and_audited(
        self,
        client: TestClient,
        lot: Callable[..., Json],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        heap = lot(close=False, bales=1)["heap"]
        row = bale_rows(client, heap["heap_id"])[0]
        officer, admin = as_officer("PK-MUL-01"), as_officer("ADMIN-01")
        assert (
            client.post(
                f"{QR}/tokens/{row['token']}/revoke", json={"reason": "x"}, headers=officer
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"{QR}/tokens/{row['token']}/revoke", json={"reason": " "}, headers=admin
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"{QR}/bales/{row['bale_serial']}/regenerate", json={"reason": "x"}, headers=officer
            ).status_code
            == 403
        )
        new = client.post(
            f"{QR}/bales/{row['bale_serial']}/regenerate",
            json={"reason": "Label smudged"},
            headers=admin,
        ).json()
        assert new["token"] != row["token"]
        assert client.get(f"{QR}/public/{row['token']}").status_code == 404
        assert client.get(f"{QR}/public/{new['token']}").status_code == 200
        db = client.app.state.db  # type: ignore[attr-defined]
        from shared.models.audit_log import AuditLog

        with db.session_scope() as s:
            actions = sorted(
                a.action
                for a in s.execute(select(AuditLog).where(AuditLog.entity == "qr_token")).scalars()
            )
            assert actions == ["regenerate", "revoke"]


class TestInternal:
    def test_lineage_of_the_seeded_lot(
        self,
        client: TestClient,
        lot: Callable[..., Json],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        data = lot()
        serial = f"{data['heap']['heap_id']}-001"
        body = client.get(f"{QR}/trace/bale/{serial}", headers=as_officer("PK-MUL-01")).json()
        assert body["bale"]["serial"] == serial
        assert sorted(f["pct"] for f in body["farmers"]) == [20.0, 30.0, 50.0]
        assert sorted(f["kg"] for f in body["farmers"]) == [2000.0, 3000.0, 5000.0]
        assert len(body["deliveries"]) == len(body["fields"]) == 3
        field = body["fields"][0]
        assert field["geometry"]["type"] == "Polygon"
        assert field["area_acre"] > 0
        assert field["fieldbook"]["status"] == "submitted"
        assert len(field["log"]) >= 11
        assert field["log"][0]["officer"] == "Muhammad Imran Khan"
        mine = body["farmers"][0]
        assert mine["sensitive_visible"] is True
        assert mine["id_number"].startswith("35202-")
        assert "*" not in mine["id_number"]
        other = client.get(f"{QR}/trace/bale/{serial}", headers=as_officer("PK-BWP-01")).json()[
            "farmers"
        ][0]
        assert other["sensitive_visible"] is False
        assert other["id_number"] != mine["id_number"]
        heap_view = client.get(f"{QR}/trace/heap/{data['heap']['heap_id']}").json()
        assert heap_view["bale"] is None
        assert heap_view["heap"]["bales_made"] == 20

    def test_resolve_every_input(self, client: TestClient, lot: Callable[..., Json]) -> None:
        heap = lot(close=False, bales=1)["heap"]
        row = bale_rows(client, heap["heap_id"])[0]
        for q in (
            row["token"],
            row["token"].lower(),
            row["bale_serial"],
            row["trace_url"],
            f"https://sawie.example/trace/{row['token']}?x=1",
        ):
            r = client.get(f"{QR}/resolve", params={"q": q}).json()
            assert (r["kind"], r["bale_serial"], r["token"]) == (
                "bale",
                row["bale_serial"],
                row["token"],
            ), q
        lot_r = client.get(f"{QR}/resolve", params={"q": heap["heap_id"]}).json()
        assert (lot_r["kind"], lot_r["heap_id"]) == ("heap", heap["heap_id"])
        assert client.get(f"{QR}/resolve", params={"q": "NOPE"}).status_code == 404

    def test_public_api(self, client: TestClient, lot: Callable[..., Json]) -> None:
        heap = lot()["heap"]
        serial = f"{heap['heap_id']}-001"
        db = client.app.state.db  # type: ignore[attr-defined]
        with db.session_scope() as s:
            token = api.get_token_for_bale(s, serial)
            assert token is not None
            assert token.trace_url.endswith(f"/trace/{token.token}")
            public = api.get_trace_for_token(s, token.token)
            assert public is not None
            assert public["bale_serial"] == serial
            internal = api.get_trace_for_token(s, token.token, public=False)
            assert internal is not None
            assert len(internal["farmers"]) == 3
            assert api.count_active_tokens(s, api.TokenQuery(heap_id=heap["heap_id"])) == 21
            assert api.get_scan_summary(s).total == 0
