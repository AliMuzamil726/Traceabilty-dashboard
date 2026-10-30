"""Fixtures for Module 7 tests (a copy of the Module 5 and 6 helpers: modules may not share tests).

Farmers, fields, fieldbooks and Radar pickup requests are created through the HTTP APIs
of Modules 2, 3 and 4, as an officer would, so these tests never touch another module's
tables.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

DL = "/api/v1/deliveries"
REG = "/api/v1/register"
FB = "/api/v1/fieldbook"
RADAR = "/api/v1/radar"
_M = 111_320.0
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YEAR = date.today().year


def _word(n: int) -> str:
    letters = "abcdefghijklmnopqrstuvwxyz"
    return letters[n // 26 % 26] + letters[n % 26]


def d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def cotton_steps() -> dict[str, Any]:
    """A complete, valid cotton fieldbook, sown 140 days ago."""
    return {
        "field_info": {
            "crop_season": "kharif",
            "area_sown": 9.5,
            "soil_texture": "loam",
            "drainage_status": "well_drained",
        },
        "land_preparation": [
            {
                "operation_date": d(160),
                "operation_type": "deep_ploughing",
                "machinery_type": "tractor_owned",
                "passes": 2,
                "tillage_depth": 25,
                "area_covered": 9.5,
                "diesel_per_pass": 6,
                "residue_handling": "incorporated",
                "cover_crop": "none",
            }
        ],
        "sowing": {
            "sowing_date": d(140),
            "variety": "fh-142",
            "seed_source": "registered_dealer",
            "seed_rate": 8,
            "sowing_method": "bed_and_furrow",
            "sowing_equipment": "seed_drill",
            "plant_population": 22000,
        },
        "nutrient_management": [
            {
                "application_date": d(130),
                "product": "urea",
                "n_content": 46,
                "pk_content": {"p2o5": 0, "k2o": 0},
                "quantity": 50,
                "crop_stage": "seedling",
            }
        ],
        "irrigation": [
            {
                "irrigation_date": d(120),
                "source": "tubewell_diesel",
                "method": "furrow",
                "duration": 6,
                "water_applied": 75,
                "diesel_used": 20,
                "pumping_head": 18,
                "pump_efficiency": 55,
            }
        ],
        "weed_management": [{"weed_date": d(110), "method": "manual_weeding"}],
        "pest_disease": [
            {
                "product_applied": "Imidacloprid",
                "product_type": "insecticide",
                "ai_content": 20,
                "dose": 250,
                "area_sprayed": 9.5,
                "pheromone_traps": 4,
                "beneficial_insects": ["lacewing", "spiders"],
            }
        ],
        "harvest": [
            {
                "picking_date": d(5),
                "picking_number": "1st",
                "harvest_method": "manual_picking",
                "yield": 12,
                "moisture": 9,
                "storage_material": "cotton_cloth",
                "ready_for_pickup": "yes",
            }
        ],
        "energy": {"total_diesel": 180, "grid_electricity": 0},
        "labour_social": {
            "family_labour": 3,
            "hired_labour": 10,
            "women_pickers": 8,
            "picking_wage": 1200,
            "training_attended": "no",
        },
    }


def square(centre: tuple[float, float], side_m: float = 200.0) -> dict[str, Any]:
    lat, lng = centre
    dl, dg = side_m / 2 / _M, side_m / 2 / (_M * math.cos(math.radians(lat)))
    w, e, s, n = lng - dg, lng + dg, lat - dl, lat + dl
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


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
def make_request(
    client: TestClient, as_officer: Callable[[str], dict[str, str]]
) -> Callable[..., dict[str, Any]]:
    """A farmer with a field that is ready, plus an open Radar pickup request for it.

    Returns ``{farmer, field, headers, request}``.
    """
    counter = {"n": 0}

    def _make(
        crop: str = "cotton",
        *,
        officer: str | None = None,
        request: bool = True,
        submit: bool = False,
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
                "district_code": "PK-PB-MUL",
                "tehsil_code": "PK-PB-MUL-T01",
                "village": "Basti Malook",
                "field_office_id": office["id"],
                "variety": "fh-142",
                "tenure": "owner",
                "previous_crop": "wheat",
            }
            centre = (30.1575 + n * 0.02, 71.5249)
            sowing = {
                "sowing_date": d(140),
                "variety": "fh-142",
                "seed_source": "registered_dealer",
                "seed_rate": 8,
                "sowing_method": "bed_and_furrow",
                "sowing_equipment": "seed_drill",
                "plant_population": 22000,
            }
        else:
            body = {
                "crop": "hemp",
                "id_number": f"{100000000 + n}",
                "name": f"grower {_word(n)}",
                "farm_name": "Fen End Farm",
                "phone": "07700 900123",
                "home_office_licence_no": f"HO-D-{n:04d}",
                "postcode": "ln4 3qp",
                "field_office_id": office["id"],
                "variety": "futura_75",
                "tenure": "owner_occupier",
                "previous_crop": "winter_wheat",
            }
            centre = (53.2307 + n * 0.02, -0.5406)
            sowing = {
                "drilling_date": d(100),
                "crop_purpose": "fibre",
                "variety": "futura_75",
                "seed_lot": "LOT-1",
                "seed_rate": 45,
                "drill_type": "combine_drill",
                "row_width": 12.5,
                "drilling_depth": 2.5,
            }
        r = client.post(f"{REG}/farmers", json=body, headers=headers)
        assert r.status_code in (200, 201), r.text
        farmer = r.json()["farmer"]
        field = client.post(
            f"{REG}/farmers/{farmer['id']}/fields",
            json={"geometry": square(centre)},
            headers=headers,
        ).json()
        book = client.post(
            f"{FB}/books", json={"field_id": field["id"], "season_year": YEAR}, headers=headers
        ).json()
        if submit:
            # A complete cotton fieldbook, submitted (and therefore locked).
            for key, value in cotton_steps().items():
                for entry in value if isinstance(value, list) else [value]:
                    url = f"{FB}/books/{book['id']}/steps/{key}"
                    r = (
                        client.post(f"{url}/entries", json={"data": entry}, headers=headers)
                        if isinstance(value, list)
                        else client.put(url, json={"data": entry}, headers=headers)
                    )
                    assert r.status_code in (200, 201), (key, r.text)
            done = client.post(f"{FB}/books/{book['id']}/submit", headers=headers)
            assert done.status_code == 200, done.text
        else:
            sr = client.put(
                f"{FB}/books/{book['id']}/steps/sowing", json={"data": sowing}, headers=headers
            )
            assert sr.status_code == 200, sr.text
        out: dict[str, Any] = {"farmer": farmer, "field": field, "headers": headers, "crop": crop}
        if request:
            rr = client.post(
                f"{RADAR}/pickup-requests",
                headers=headers,
                json={"crop": crop, "season_year": YEAR, "field_ids": [field["id"]]},
            )
            assert rr.status_code == 201, rr.text
            assert rr.json()["created"], rr.text
            out["request"] = rr.json()["created"][0]
        return out

    return _make


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
def schedule(client: TestClient, sites: dict[str, str]) -> Callable[..., dict[str, Any]]:
    """Schedule one farm's request at a site. Returns the created delivery."""

    def _schedule(farm: dict[str, Any], site: str | None = None, **over: Any) -> dict[str, Any]:
        code = site or ("BWP-G1" if farm["crop"] == "cotton" else "UK-P1")
        body = {
            "request_ids": [farm["request"]["id"]],
            **transport(sites[code], farm["crop"], **over),
        }
        r = client.post(f"{DL}/schedule", json=body, headers=farm["headers"])
        assert r.status_code == 201, r.text
        assert r.json()["created"], r.json()
        return r.json()["created"][0]

    return _schedule


@pytest.fixture
def deliver(
    client: TestClient, schedule: Callable[..., dict[str, Any]]
) -> Callable[..., dict[str, Any]]:
    """Schedule, dispatch and receive. Returns the delivered delivery detail."""

    def _deliver(
        farm: dict[str, Any],
        *,
        site: str | None = None,
        weighbridge: float | None = None,
        moisture: float = 9.0,
    ) -> dict[str, Any]:
        dl = schedule(farm, site)
        h = farm["headers"]
        client.post(f"{DL}/{dl['id']}/dispatch", json={}, headers=h)
        weight = weighbridge or dl["estimated_quantity_kg"]
        r = client.post(
            f"{DL}/{dl['id']}/receive",
            json={"weighbridge_weight_kg": weight, "moisture_pct": moisture, "note": "Test load"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        return r.json()["delivery"]

    return _deliver


HEAPS = "/api/v1/heaps"


@pytest.fixture
def delivered(
    client: TestClient,
    make_request: Callable[..., dict[str, Any]],
    deliver: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    """A delivered delivery at ``site`` weighing ``kg``. Returns the delivery detail."""

    def _make(
        kg: float, *, site: str = "BWP-G1", crop: str = "cotton", officer: str | None = None
    ) -> dict[str, Any]:
        return deliver(make_request(crop, officer=officer), site=site, weighbridge=kg)

    return _make


@pytest.fixture
def open_heap(
    client: TestClient, sites: dict[str, str], as_officer: Callable[[str], dict[str, str]]
) -> Callable[..., dict[str, Any]]:
    def _open(site: str = "BWP-G1", officer: str = "PK-MUL-01") -> dict[str, Any]:
        r = client.post(HEAPS, json={"site_id": sites[site]}, headers=as_officer(officer))
        assert r.status_code == 201, r.text
        return r.json()["heap"]

    return _open


QR = "/api/v1/qr"
