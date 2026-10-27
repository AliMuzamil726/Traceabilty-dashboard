"""Fixtures for Module 4 tests.

Farmers, fields and fieldbooks are created through Modules 2 and 3's HTTP APIs, as an
officer would, so these tests never touch another module's tables.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from module_4.services import cache

RADAR = "/api/v1/radar"
REG = "/api/v1/register"
FB = "/api/v1/fieldbook"
MULTAN = (30.1575, 71.5249)
LINCOLNSHIRE = (53.2307, -0.5406)
_M = 111_320.0


def _word(n: int) -> str:
    """Names may hold letters only, so number the test farmers with letters."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    return letters[n // 26 % 26] + letters[n % 26]


def d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


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


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    cache.invalidate()
    yield
    cache.invalidate()


@pytest.fixture
def officer_ids(client: TestClient) -> dict[str, str]:
    page = client.get("/api/v1/officers", params={"page_size": 200}).json()
    return {o["code"]: o["id"] for o in page["items"]}


@pytest.fixture
def as_officer(officer_ids: dict[str, str]) -> Callable[[str], dict[str, str]]:
    return lambda code: {"X-Officer-Id": officer_ids[code]}


@pytest.fixture
def make_farm(
    client: TestClient, as_officer: Callable[[str], dict[str, str]]
) -> Callable[..., dict[str, Any]]:
    """Register a farmer with one field, optionally sown ``sown`` days ago.

    Returns ``{farmer, field, headers, book}``.
    """
    counter = {"n": 0}

    def _make(
        crop: str = "cotton",
        *,
        sown: int | None = None,
        officer: str | None = None,
        harvest: dict[str, Any] | None = None,
        district: str | None = None,
    ) -> dict[str, Any]:
        counter["n"] += 1
        n = counter["n"]
        code = officer or ("PK-MUL-01" if crop == "cotton" else "GB-EOE-01")
        headers = as_officer(code)
        country = "PK" if crop == "cotton" else "GB"
        office = client.get("/api/v1/offices", params={"country": country}).json()["items"][0]
        if crop == "cotton":
            body = {
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
                "home_office_licence_no": f"HO-R-{n:04d}",
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
        fr = client.post(
            f"{REG}/farmers/{farmer['id']}/fields",
            json={"geometry": square(centre)},
            headers=headers,
        )
        assert fr.status_code == 201, fr.text
        field = fr.json()
        book = None
        if sown is not None or harvest is not None:
            br = client.post(
                f"{FB}/books",
                json={"field_id": field["id"], "season_year": date.today().year},
                headers=headers,
            )
            book = br.json()
        if sown is not None:
            data = cotton_sowing(sown) if crop == "cotton" else hemp_sowing(sown)
            sr = client.put(
                f"{FB}/books/{book['id']}/steps/sowing", json={"data": data}, headers=headers
            )  # type: ignore[index]
            assert sr.status_code == 200, sr.text
        if harvest is not None:
            hr = client.post(
                f"{FB}/books/{book['id']}/steps/harvest/entries",
                json={"data": harvest},  # type: ignore[index]
                headers=headers,
            )
            assert hr.status_code == 201, hr.text
        return {"farmer": farmer, "field": field, "headers": headers, "book": book, "crop": crop}

    return _make


@pytest.fixture
def radar(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _get(headers: dict[str, str], **params: Any) -> dict[str, Any]:
        r = client.get(f"{RADAR}/fields", params={"page_size": 100, **params}, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    return _get


def row_for(page: dict[str, Any], farm: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in page["items"] if r["field_id"] == farm["field"]["id"])
