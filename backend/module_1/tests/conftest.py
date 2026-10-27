"""Fixtures for Module 1 tests.

The dashboard only adds up what the other modules recorded, so there is nothing to seed
directly: every row these tests count is created through the HTTP APIs of Modules 2 to
7, exactly as an officer would. The helpers are a copy of the ones in Modules 4 to 6,
because a module may not import another module's tests.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

DASH = "/api/v1/dashboard"
REG = "/api/v1/register"
FB = "/api/v1/fieldbook"
RADAR = "/api/v1/radar"
DL = "/api/v1/deliveries"
HEAPS = "/api/v1/heaps"
QR = "/api/v1/qr"

YEAR = date.today().year
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
MULTAN = (30.1575, 71.5249)
LINCOLNSHIRE = (53.2307, -0.5406)
_M = 111_320.0


def _word(n: int) -> str:
    """Names may hold letters only, so number the test farmers with letters."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    return letters[n // 26 % 26] + letters[n % 26]


def d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def ahead(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def square(centre: tuple[float, float], side_m: float = 200.0) -> dict[str, Any]:
    lat, lng = centre
    dl, dg = side_m / 2 / _M, side_m / 2 / (_M * math.cos(math.radians(lat)))
    w, e, s, n = lng - dg, lng + dg, lat - dl, lat + dl
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def cotton_sowing(days_ago: int) -> dict[str, Any]:
    return {
        "sowing_date": d(days_ago),
        "variety": "fh-142",
        "seed_source": "registered_dealer",
        "seed_rate": 8,
        "sowing_method": "bed_and_furrow",
        "sowing_equipment": "seed_drill",
        "plant_population": 22000,
    }


def hemp_sowing(days_ago: int) -> dict[str, Any]:
    return {
        "drilling_date": d(days_ago),
        "crop_purpose": "fibre",
        "variety": "futura_75",
        "seed_lot": "LOT-1",
        "seed_rate": 45,
        "drill_type": "combine_drill",
        "row_width": 12.5,
        "drilling_depth": 2.5,
    }


def cotton_picking(days_ago: int = 1, ready: str = "no") -> dict[str, Any]:
    return {
        "picking_date": d(days_ago),
        "picking_number": "1st",
        "harvest_method": "manual_picking",
        "yield": 12,
        "moisture": 9,
        "storage_material": "cotton_cloth",
        "ready_for_pickup": ready,
    }


@pytest.fixture
def officer_ids(client: TestClient) -> dict[str, str]:
    page = client.get("/api/v1/officers", params={"page_size": 200}).json()
    return {o["code"]: o["id"] for o in page["items"]}


@pytest.fixture
def as_officer(officer_ids: dict[str, str]) -> Callable[[str], dict[str, str]]:
    return lambda code: {"X-Officer-Id": officer_ids[code]}


@pytest.fixture
def sites(client: TestClient) -> dict[str, str]:
    return {s["code"]: s["id"] for s in client.get("/api/v1/sites").json()}


@pytest.fixture
def make_farm(
    client: TestClient, as_officer: Callable[[str], dict[str, str]]
) -> Callable[..., dict[str, Any]]:
    """A registered farmer with one mapped field, and optionally a fieldbook.

    ``sown`` opens a fieldbook and records the sowing date that many days ago;
    ``harvest`` adds a harvest entry. Returns ``{farmer, field, headers, book, crop}``.
    """
    counter = {"n": 0}

    def _make(
        crop: str = "cotton",
        *,
        sown: int | None = None,
        officer: str | None = None,
        harvest: dict[str, Any] | None = None,
        district: str | None = None,
        field: bool = True,
    ) -> dict[str, Any]:
        counter["n"] += 1
        n = counter["n"]
        code = officer or ("PK-MUL-01" if crop == "cotton" else "GB-EOE-01")
        headers = as_officer(code)
        country = "PK" if crop == "cotton" else "GB"
        office = client.get("/api/v1/offices", params={"country": country}).json()["items"][0]
        if crop == "cotton":
            body: dict[str, Any] = {
                "crop": "cotton",
                "id_number": f"35202-{n:07d}-1",
                "name": f"farmer {_word(n)}",
                "father_name": "ghulam rasool",
                "phone": "0300-1234567",
                "province_code": "PK-PB",
                "district_code": district or "PK-PB-MUL",
                "tehsil_code": f"{district or 'PK-PB-MUL'}-T01",
                "village": "Basti Malook",
                "field_office_id": office["id"],
                "variety": "fh-142",
                "tenure": "owner",
                "previous_crop": "wheat",
            }
            centre = (MULTAN[0] + n * 0.02, MULTAN[1])
        else:
            body = {
                "crop": "hemp",
                "id_number": f"{100000000 + n}",
                "name": f"grower {_word(n)}",
                "farm_name": "Fen End Farm",
                "phone": "07700 900123",
                "home_office_licence_no": f"HO-B-{n:04d}",
                "postcode": "ln4 3qp",
                "field_office_id": office["id"],
                "variety": "futura_75",
                "tenure": "owner_occupier",
                "previous_crop": "winter_wheat",
            }
            centre = (LINCOLNSHIRE[0] + n * 0.02, LINCOLNSHIRE[1])
        r = client.post(f"{REG}/farmers", json=body, headers=headers)
        assert r.status_code in (200, 201), r.text
        farmer = r.json()["farmer"]
        out: dict[str, Any] = {
            "farmer": farmer,
            "field": None,
            "headers": headers,
            "book": None,
            "crop": crop,
            "officer_code": code,
        }
        if not field:
            return out
        fr = client.post(
            f"{REG}/farmers/{farmer['id']}/fields",
            json={"geometry": square(centre)},
            headers=headers,
        )
        assert fr.status_code == 201, fr.text
        out["field"] = fr.json()
        if sown is None and harvest is None:
            return out
        br = client.post(
            f"{FB}/books",
            json={"field_id": out["field"]["id"], "season_year": YEAR},
            headers=headers,
        )
        assert br.status_code in (200, 201), br.text
        out["book"] = br.json()
        if sown is not None:
            data = cotton_sowing(sown) if crop == "cotton" else hemp_sowing(sown)
            sr = client.put(
                f"{FB}/books/{out['book']['id']}/steps/sowing",
                json={"data": data},
                headers=headers,
            )
            assert sr.status_code == 200, sr.text
        if harvest is not None:
            hr = client.post(
                f"{FB}/books/{out['book']['id']}/steps/harvest/entries",
                json={"data": harvest},
                headers=headers,
            )
            assert hr.status_code == 201, hr.text
        return out

    return _make


@pytest.fixture
def request_pickup(client: TestClient) -> Callable[..., dict[str, Any]]:
    """Ask for a pickup for one farm's field. Returns the created request."""

    def _request(farm: dict[str, Any], **body: Any) -> dict[str, Any]:
        r = client.post(
            f"{RADAR}/pickup-requests",
            headers=farm["headers"],
            json={
                "crop": farm["crop"],
                "season_year": YEAR,
                "field_ids": [farm["field"]["id"]],
                **body,
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["created"], r.text
        return r.json()["created"][0]

    return _request


def transport(site_id: str, crop: str = "cotton", **over: Any) -> dict[str, Any]:
    return {
        "site_id": site_id,
        "scheduled_date": TOMORROW,
        "driver_name": "Akram Ali",
        "driver_phone": "0301 7654321" if crop == "cotton" else "07700 900456",
        "vehicle_no": "mna-1234" if crop == "cotton" else "ab12 cde",
        **over,
    }


@pytest.fixture
def schedule(
    client: TestClient, sites: dict[str, str], request_pickup: Callable[..., dict[str, Any]]
) -> Callable[..., dict[str, Any]]:
    """Request a pickup and schedule it. Returns the created delivery."""

    def _schedule(farm: dict[str, Any], *, site: str | None = None, **over: Any) -> dict[str, Any]:
        pickup = farm.get("request") or request_pickup(farm)
        farm["request"] = pickup
        code = site or ("BWP-G1" if farm["crop"] == "cotton" else "UK-P1")
        r = client.post(
            f"{DL}/schedule",
            json={
                "request_ids": [pickup["id"]],
                **transport(sites[code], farm["crop"], **over),
            },
            headers=farm["headers"],
        )
        assert r.status_code == 201, r.text
        assert r.json()["created"], r.text
        return r.json()["created"][0]

    return _schedule


@pytest.fixture
def deliver(
    client: TestClient, schedule: Callable[..., dict[str, Any]]
) -> Callable[..., dict[str, Any]]:
    """Schedule, dispatch and receive one farm's load. Returns the delivered record."""

    def _deliver(
        farm: dict[str, Any],
        *,
        site: str | None = None,
        weighbridge: float | None = None,
        moisture: float = 9.0,
        field_weight: float | None = None,
    ) -> dict[str, Any]:
        dl = schedule(farm, site=site)
        headers = farm["headers"]
        client.post(
            f"{DL}/{dl['id']}/dispatch",
            json={} if field_weight is None else {"field_weight_kg": field_weight},
            headers=headers,
        )
        weight = weighbridge if weighbridge is not None else dl["estimated_quantity_kg"]
        r = client.post(
            f"{DL}/{dl['id']}/receive",
            json={
                "weighbridge_weight_kg": weight,
                "moisture_pct": moisture,
                "note": "Test load",
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        return r.json()["delivery"]

    return _deliver


@pytest.fixture
def heap_with_bales(
    client: TestClient, sites: dict[str, str], as_officer: Callable[[str], dict[str, str]]
) -> Callable[..., dict[str, Any]]:
    """Open a heap, add delivered loads and record bales. Returns the heap detail."""

    def _make(
        deliveries: list[dict[str, Any]],
        *,
        site: str = "BWP-G1",
        officer: str = "PK-MUL-01",
        bales: int = 0,
    ) -> dict[str, Any]:
        headers = as_officer(officer)
        opened = client.post(HEAPS, json={"site_id": sites[site]}, headers=headers)
        assert opened.status_code == 201, opened.text
        heap = opened.json()["heap"]
        if deliveries:
            added = client.post(
                f"{HEAPS}/{heap['heap_id']}/deliveries",
                json={"delivery_ids": [d["id"] for d in deliveries]},
                headers=headers,
            )
            assert added.status_code == 200, added.text
        if bales:
            made = client.post(
                f"{HEAPS}/{heap['heap_id']}/bales", json={"count": bales}, headers=headers
            )
            assert made.status_code == 201, made.text
        detail = client.get(f"{HEAPS}/{heap['heap_id']}", headers=headers)
        assert detail.status_code == 200, detail.text
        return detail.json()

    return _make


@pytest.fixture
def dashboard(client: TestClient) -> Callable[..., dict[str, Any]]:
    """Read one dashboard section and assert it answered."""

    def _get(section: str, headers: dict[str, str], **params: Any) -> dict[str, Any]:
        r = client.get(f"{DASH}/{section}", params=params, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    return _get


def stage(pipeline: dict[str, Any], key: str) -> dict[str, Any]:
    return next(s for s in pipeline["stages"] if s["key"] == key)


def alert(alerts: dict[str, Any], key: str) -> dict[str, Any]:
    return next(a for a in alerts["alerts"] if a["key"] == key)
